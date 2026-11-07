"""Bounded newline-delimited JSON transport; block hashes remain binary-defined."""

import asyncio
from ipaddress import IPv4Address, IPv4Network
import json


MAX_MESSAGE = 16384
BATCH_SIZE = 32
PRIVATE_NETWORKS = tuple(IPv4Network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))
FIELDS = {
    "hello": {"type", "version", "network_id", "genesis", "node_id", "head"},
    "head": {"type", "hash"},
    "block": {"type", "header"},
    "get_chain": {"type", "head", "locator"},
    "chain": {"type", "head", "headers"},
}


def endpoint(value: str) -> tuple[str, int]:
    host, separator, port_text = value.rpartition(":")
    if not separator:
        raise ValueError("endpoint must be an IPv4 address followed by :port")
    address = IPv4Address(host)
    if not address.is_loopback and not any(address in network for network in PRIVATE_NETWORKS):
        raise ValueError("only loopback and private LAN IPv4 addresses are allowed")
    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return str(address), port


def binary(value: object, length: int) -> bytes:
    if type(value) is not str or len(value) != length * 2 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"expected {length} bytes encoded as lowercase hexadecimal")
    return bytes.fromhex(value)


async def read_message(reader: asyncio.StreamReader) -> dict:
    line = await reader.readline()
    if not line:
        raise ConnectionError("peer closed the connection")
    if len(line) > MAX_MESSAGE or not line.endswith(b"\n"):
        raise ValueError("invalid message framing or size")
    message = json.loads(line)
    if type(message) is not dict or type(message.get("type")) is not str:
        raise ValueError("message must be an object with a string type")
    kind = message["type"]
    if kind not in FIELDS or set(message) != FIELDS[kind]:
        raise ValueError("unknown message type or incorrect fields")
    return message


def encode_message(message: dict) -> bytes:
    data = json.dumps(message, separators=(",", ":")).encode("ascii") + b"\n"
    if len(data) > MAX_MESSAGE:
        raise ValueError("outgoing message exceeds size limit")
    return data
