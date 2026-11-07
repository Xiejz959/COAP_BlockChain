"""Fixed-width, big-endian block headers."""

from dataclasses import dataclass
from hashlib import sha256
from struct import Struct


HEADER = Struct(">H16s32sQ16s32sQ")
ZERO_HASH = bytes(32)
GENESIS_NODE_ID = bytes(16)
MAX_HEIGHT = (1 << 63) - 1
MAX_NONCE = (1 << 64) - 1
MAX_TARGET = (1 << 256) - 1


@dataclass(frozen=True, slots=True)
class Block:
    version: int
    network_id: bytes
    previous_hash: bytes
    height: int
    node_id: bytes
    target: int
    nonce: int

    def __post_init__(self) -> None:
        for name, limit in (
            ("version", (1 << 16) - 1),
            ("height", MAX_HEIGHT),
            ("target", MAX_TARGET),
            ("nonce", MAX_NONCE),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= limit:
                raise ValueError(f"invalid {name}")
        for name, length in (
            ("network_id", 16),
            ("previous_hash", 32),
            ("node_id", 16),
        ):
            value = getattr(self, name)
            if type(value) is not bytes or len(value) != length:
                raise ValueError(f"{name} must contain exactly {length} bytes")

    def to_bytes(self) -> bytes:
        return HEADER.pack(
            self.version,
            self.network_id,
            self.previous_hash,
            self.height,
            self.node_id,
            self.target.to_bytes(32, "big"),
            self.nonce,
        )

    @classmethod
    def from_bytes(cls, header: bytes) -> "Block":
        if len(header) != HEADER.size:
            raise ValueError(f"block header must contain {HEADER.size} bytes")
        version, network, previous, height, node, target, nonce = HEADER.unpack(header)
        return cls(version, network, previous, height, node, int.from_bytes(target, "big"), nonce)

    @property
    def hash(self) -> bytes:
        return sha256(self.to_bytes()).digest()
