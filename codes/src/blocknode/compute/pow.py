"""Search a finite uint64 nonce space using hashlib SHA-256."""

from dataclasses import dataclass, replace
from hashlib import sha256
from time import perf_counter

from blocknode.chain.block import Block, MAX_NONCE
from blocknode.chain.config import NetworkConfig


@dataclass(frozen=True, slots=True)
class ComputationResult:
    block: Block
    attempts: int
    elapsed_seconds: float


def compute_block(parent: Block, config: NetworkConfig, node_id: bytes) -> ComputationResult:
    candidate = Block(
        config.version, config.network_id, parent.hash, parent.height + 1,
        node_id, config.target, 0,
    )
    started = perf_counter()
    block = search_nonces(candidate, 0, MAX_NONCE + 1)
    if block is not None:
        return ComputationResult(block, block.nonce + 1, perf_counter() - started)
    raise RuntimeError("nonce space exhausted without a valid result")


def search_nonces(candidate: Block, start: int, stop: int) -> Block | None:
    prefix = candidate.to_bytes()[:-8]
    target_bytes = candidate.target.to_bytes(32, "big")
    for nonce in range(start, stop):
        digest = sha256(prefix + nonce.to_bytes(8, "big")).digest()
        if digest <= target_bytes:
            return replace(candidate, nonce=nonce)
    return None
