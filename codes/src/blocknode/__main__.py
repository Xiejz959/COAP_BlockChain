"""Run finite local computation, optionally serving configured private peers."""

import argparse
import asyncio
from pathlib import Path
import sqlite3

from blocknode.chain.config import load_config
from blocknode.compute.pow import compute_block
from blocknode.storage.sqlite import BlockStore
from blocknode.network.node import NetworkNode
from blocknode.network.protocol import endpoint


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or a positive integer")
    return number


def run(config_path: Path, data_dir: Path, blocks: int, listen=None, peers=()) -> None:
    config = load_config(config_path)
    store = BlockStore(data_dir, config)
    try:
        print(
            f"START height={store.tip.height} accepted_block_count={store.accepted_block_count} "
            f"head={store.tip.hash.hex()} node_id={store.node_id.hex()}", flush=True,
        )
        if listen is not None:
            try:
                asyncio.run(NetworkNode(store, listen, list(peers)).run(blocks))
            except KeyboardInterrupt:
                pass
            return
        for _ in range(blocks):
            result = compute_block(store.tip, config, store.node_id)
            store.accept(result.block)
            print(
                f"BLOCK height={store.tip.height} accepted_block_count={store.accepted_block_count} "
                f"hash={store.tip.hash.hex()} nonce={store.tip.nonce} "
                f"attempts={result.attempts} compute_seconds={result.elapsed_seconds:.6f}",
                flush=True,
            )
    finally:
        print(
            f"STOP height={store.tip.height} accepted_block_count={store.accepted_block_count} "
            f"head={store.tip.hash.hex()}", flush=True,
        )
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m blocknode", description="Educational local-network PoW block computation",
    )
    parser.add_argument("--config", required=True, type=Path, help="shared genesis JSON configuration")
    parser.add_argument("--data-dir", required=True, type=Path, help="independent node data directory")
    parser.add_argument(
        "--blocks", type=nonnegative_int, default=0,
        help="number of additional blocks to compute; 0 validates and displays stored state",
    )
    parser.add_argument("--listen", type=endpoint, help="listen IPv4:port; defaults to no network server")
    parser.add_argument("--peer", type=endpoint, action="append", default=[], help="explicit peer IPv4:port; repeatable")
    args = parser.parse_args()
    if args.peer and args.listen is None:
        parser.error("--peer requires --listen")
    if args.listen in args.peer or len(set(args.peer)) != len(args.peer):
        parser.error("peers must be distinct and cannot equal the listen address")
    try:
        run(args.config, args.data_dir, args.blocks, args.listen, args.peer)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
