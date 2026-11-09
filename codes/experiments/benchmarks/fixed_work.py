"""Measure the reference PoW loop over a fixed range without early exit."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timezone
from hashlib import sha256
import json
from multiprocessing import get_context
from pathlib import Path
import platform
import ssl
from time import perf_counter_ns

from blocknode.chain.block import Block, MAX_NONCE
from blocknode.chain.config import load_config


def scan_range(prefix: bytes, target: bytes, start: int, stop: int) -> tuple[int, str]:
    hits = 0
    for nonce in range(start, stop):
        digest = sha256(prefix + nonce.to_bytes(8, "big")).digest()
        if digest <= target:
            hits += 1
    return hits, digest.hex()


def run_trial(prefix: bytes, target: bytes, attempts: int, workers: int, pool) -> dict:
    started = perf_counter_ns()
    if pool is None:
        hits, last_digest = scan_range(prefix, target, 0, attempts)
    else:
        jobs = [pool.submit(scan_range, prefix, target,
                            attempts * index // workers, attempts * (index + 1) // workers)
                for index in range(workers)]
        results = [job.result() for job in jobs]
        hits = sum(count for count, _ in results)
        last_digest = results[-1][1]
    elapsed_ns = perf_counter_ns() - started
    return {
        "elapsed_ns": elapsed_ns,
        "hashes_per_second": attempts * 1_000_000_000 / elapsed_ns,
        "target_hits": hits,
        "last_digest": last_digest,
    }


def fixed_header(config) -> bytes:
    return Block(
        config.version, config.network_id, config.genesis().hash, 1,
        bytes.fromhex("11" * 16), config.target, 0,
    ).to_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device", required=True, help="label for this device in the results")
    parser.add_argument("--attempts", type=int, required=True)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.attempts <= MAX_NONCE + 1:
        parser.error("--attempts must fit the uint64 nonce space and be positive")
    if args.warmups < 0 or args.runs < 1:
        parser.error("--warmups must be nonnegative and --runs must be positive")
    if not 1 <= args.workers <= args.attempts:
        parser.error("--workers must be positive and cannot exceed --attempts")

    config = load_config(args.config)
    header = fixed_header(config)
    prefix = header[:-8]
    target = config.target.to_bytes(32, "big")
    started_at = datetime.now(timezone.utc).isoformat()
    pool_context = (ProcessPoolExecutor(args.workers, mp_context=get_context("spawn"))
                    if args.workers > 1 else nullcontext())
    with pool_context as pool:
        warmups = [run_trial(prefix, target, args.attempts, args.workers, pool)
                   for _ in range(args.warmups)]
        measurements = [run_trial(prefix, target, args.attempts, args.workers, pool)
                        for _ in range(args.runs)]

    print(json.dumps({
        "device": args.device,
        "started_at_utc": started_at,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "sha256_backend": type(sha256()).__module__,
        "openssl": ssl.OPENSSL_VERSION,
        "header_nonce_zero_hex": header.hex(),
        "first_nonce": 0,
        "attempts_per_trial": args.attempts,
        "workers": args.workers,
        "warmups": warmups,
        "measurements": measurements,
    }, indent=2))


if __name__ == "__main__":
    main()
