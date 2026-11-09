"""Measure TCP catch-up on the receiver while local PoW workers compete for CPU."""

import argparse
import asyncio
from contextlib import redirect_stdout, suppress
from datetime import datetime, timezone
from io import StringIO
import json
from multiprocessing import get_context
from pathlib import Path
import platform
from random import Random
from tempfile import TemporaryDirectory
from time import perf_counter_ns, process_time_ns

from blocknode.chain.config import load_config
from blocknode.network.node import NetworkNode
from blocknode.network.protocol import binary, endpoint
from blocknode.storage.sqlite import BlockStore
from fixed_work import fixed_header, scan_range


LOADS = (0, 1, 4)
ORDER_SEED = 1110
CHUNK_SIZE = 4096


class TimedStore(BlockStore):
    def __init__(self, directory, config):
        super().__init__(directory, config)
        self.accept_times = []

    def accept(self, block):
        started = perf_counter_ns()
        accepted = super().accept(block)
        if accepted:
            self.accept_times.append(perf_counter_ns() - started)
        return accepted


class MeasuredNode(NetworkNode):
    def __init__(self, store, peer, expected_head):
        super().__init__(store, ("127.0.0.1", 0), [peer])
        self.expected_head = expected_head
        self.finished = asyncio.Event()

    async def connect(self, peer):
        self.started_ns = perf_counter_ns()
        self.cpu_started_ns = process_time_ns()
        await super().connect(peer)

    def accept(self, block, source):
        accepted = super().accept(block, source)
        if accepted and self.store.tip.hash == self.expected_head:
            self.catchup_ns = perf_counter_ns() - self.started_ns
            self.receiver_cpu_ns = process_time_ns() - self.cpu_started_ns
            self.finished.set()
        return accepted


def hash_load(prefix, target, index, workers, ready, stop):
    start = index * CHUNK_SIZE
    while not stop.is_set():
        scan_range(prefix, target, start, start + CHUNK_SIZE)
        if not ready.is_set():
            ready.set()
        start += workers * CHUNK_SIZE


async def catch_up(store, peer, expected_head, expected_height):
    node = MeasuredNode(store, peer, expected_head)
    with redirect_stdout(StringIO()):
        service = asyncio.create_task(node.run(0))
        try:
            await asyncio.wait_for(node.finished.wait(), timeout=10)
        finally:
            service.cancel()
            with suppress(asyncio.CancelledError):
                await service
    if (store.tip.height != expected_height or store.tip.hash != expected_head
            or len(store.accept_times) != expected_height):
        raise RuntimeError("receiver did not accept exactly the expected chain")
    return {
        "connect_to_accept_ns": node.catchup_ns,
        "receiver_cpu_ns": node.receiver_cpu_ns,
        "store_accept_ns": store.accept_times,
        "height": store.tip.height,
        "head": store.tip.hash.hex(),
    }


def measure(config, peer, expected_head, expected_height, workers):
    context = get_context("spawn")
    stop = context.Event()
    active = []
    header = fixed_header(config)
    with TemporaryDirectory(prefix="sync-bench-", dir=Path.cwd()) as directory:
        store = TimedStore(Path(directory), config)
        try:
            for index in range(workers):
                ready = context.Event()
                process = context.Process(target=hash_load, args=(
                    header[:-8], header[-40:-8], index, workers, ready, stop,
                ))
                process.start()
                active.append((process, ready))
            for _, ready in active:
                if not ready.wait(timeout=10):
                    raise RuntimeError("a load worker did not begin hashing")
            result = asyncio.run(catch_up(store, peer, expected_head, expected_height))
        finally:
            stop.set()
            for process, _ in active:
                process.join()
            store.close()
    if any(process.exitcode != 0 for process, _ in active):
        raise RuntimeError("a load worker failed during the trial")
    return {"workers": workers, **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--peer", type=endpoint, required=True)
    parser.add_argument("--head", type=lambda value: binary(value, 32), required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--trials", type=int, default=30)
    args = parser.parse_args()
    if args.height < 1 or args.trials < 1:
        parser.error("--height and --trials must be positive")

    config = load_config(args.config)
    started_at = datetime.now(timezone.utc).isoformat()
    warmups = [measure(config, args.peer, args.head, args.height, count) for count in LOADS]
    rng = Random(ORDER_SEED)
    measurements = []
    for repetition in range(1, args.trials + 1):
        order = list(LOADS)
        rng.shuffle(order)
        for workers in order:
            result = measure(config, args.peer, args.head, args.height, workers)
            measurements.append({"repetition": repetition, **result})

    print(json.dumps({
        "started_at_utc": started_at,
        "receiver_platform": platform.platform(),
        "receiver_python": platform.python_version(),
        "blocks_per_trial": args.height,
        "expected_head": args.head.hex(),
        "order_seed": ORDER_SEED,
        "warmups": warmups,
        "measurements": measurements,
    }, indent=2))


if __name__ == "__main__":
    main()
