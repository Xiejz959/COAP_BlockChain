"""Validation for a direct extension of a known parent."""

from .block import Block, GENESIS_NODE_ID
from .config import NetworkConfig


def validate_header(block: Block, config: NetworkConfig) -> None:
    if block.version != config.version or block.network_id != config.network_id:
        raise ValueError("block protocol or network does not match configuration")
    if block.target != config.target:
        raise ValueError("block target does not match the network target")
    if block.node_id == GENESIS_NODE_ID:
        raise ValueError("the zero node ID is reserved for genesis")
    if int.from_bytes(block.hash, "big") > config.target:
        raise ValueError("block does not satisfy PoW")


def validate_block(block: Block, parent: Block, config: NetworkConfig) -> None:
    validate_header(block, config)
    if block.height != parent.height + 1:
        raise ValueError("block height must equal parent height plus one")
    if block.previous_hash != parent.hash:
        raise ValueError("block previous_hash does not match parent")
