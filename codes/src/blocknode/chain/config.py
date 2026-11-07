"""Explicit, shared network and genesis configuration."""

from dataclasses import dataclass
import json
from pathlib import Path

from .block import Block, GENESIS_NODE_ID, MAX_NONCE, MAX_TARGET, ZERO_HASH


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    version: int
    network_id: bytes
    target: int
    genesis_nonce: int

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version != 1:
            raise ValueError("only protocol version 1 is supported")
        if type(self.network_id) is not bytes or len(self.network_id) != 16:
            raise ValueError("network_id must contain exactly 16 ASCII bytes")
        self.network_id.decode("ascii")
        if type(self.target) is not int or not 0 < self.target <= MAX_TARGET:
            raise ValueError("target must be a positive 256-bit integer")
        if type(self.genesis_nonce) is not int or not 0 <= self.genesis_nonce <= MAX_NONCE:
            raise ValueError("invalid genesis_nonce")

    def genesis(self) -> Block:
        block = Block(
            self.version, self.network_id, ZERO_HASH, 0,
            GENESIS_NODE_ID, self.target, self.genesis_nonce,
        )
        if int.from_bytes(block.hash, "big") > self.target:
            raise ValueError("configured genesis does not satisfy PoW")
        return block


def load_config(path: Path) -> NetworkConfig:
    values = json.loads(path.read_text(encoding="utf-8"))
    fields = {"version", "network_id", "target", "genesis_nonce"}
    if type(values) is not dict or set(values) != fields:
        raise ValueError("configuration must contain version, network_id, target, genesis_nonce")
    if type(values["network_id"]) is not str:
        raise ValueError("network_id must be an ASCII string")
    target = values["target"]
    if type(target) is not str or len(target) != 64 or any(
        character not in "0123456789abcdef" for character in target
    ):
        raise ValueError("target must contain exactly 64 lowercase hexadecimal characters")
    config = NetworkConfig(
        values["version"], values["network_id"].encode("ascii"),
        int(target, 16), values["genesis_nonce"],
    )
    config.genesis()
    return config
