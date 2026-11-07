"""TCP sessions, paginated chain sync, and cooperative reference computation."""

import asyncio
from time import perf_counter

from blocknode.chain.block import Block, HEADER, MAX_NONCE
from blocknode.chain.validation import validate_header
from blocknode.compute.pow import search_nonces
from blocknode.storage.sqlite import BlockStore
from .protocol import BATCH_SIZE, MAX_MESSAGE, binary, encode_message, read_message


class Session:
    def __init__(self, node: "NetworkNode", reader, writer) -> None:
        self.node, self.reader, self.writer = node, reader, writer
        self.sync_head: bytes | None = None
        self.next_head: bytes | None = None
        self.request_locator: list[bytes] = []

    def send(self, message: dict) -> None:
        self.writer.write(encode_message(message))

    def sync(self, head: bytes) -> None:
        if head in self.node.store.blocks:
            return
        if self.sync_head is not None:
            self.next_head = head
            return
        self.sync_head = head
        self.request(self.node.store.locator())

    def request(self, locator: list[bytes]) -> None:
        self.request_locator = locator
        self.send({"type": "get_chain", "head": self.sync_head.hex(),
                   "locator": [digest.hex() for digest in locator]})

    async def run(self) -> None:
        store = self.node.store
        config = store.config
        try:
            self.send({"type": "hello", "version": config.version,
                       "network_id": config.network_id.hex(),
                       "genesis": config.genesis().hash.hex(),
                       "node_id": store.node_id.hex(), "head": store.tip.hash.hex()})
            await self.writer.drain()
            hello = await asyncio.wait_for(read_message(self.reader), timeout=5)
            if hello["type"] != "hello":
                raise ValueError("first peer message must be hello")
            if (type(hello["version"]) is not int or hello["version"] != config.version
                    or binary(hello["network_id"], 16) != config.network_id
                    or binary(hello["genesis"], 32) != config.genesis().hash):
                raise ValueError("peer protocol, network or genesis mismatch")
            peer_id = binary(hello["node_id"], 16)
            if peer_id == store.node_id or peer_id == bytes(16):
                raise ValueError("peer node ID is self or reserved")
            head = binary(hello["head"], 32)
            self.node.sessions.add(self)
            print(f"PEER_CONNECTED node_id={peer_id.hex()}", flush=True)
            self.sync(head)
            while True:
                await self.writer.drain()
                self.handle(await read_message(self.reader))
        finally:
            self.node.sessions.discard(self)
            self.writer.close()

    def handle(self, message: dict) -> None:
        store = self.node.store
        kind = message["type"]
        if kind == "head":
            self.sync(binary(message["hash"], 32))
        elif kind == "block":
            block = Block.from_bytes(binary(message["header"], HEADER.size))
            if block.hash in store.blocks:
                return
            validate_header(block, store.config)
            if block.previous_hash not in store.blocks:
                self.sync(block.hash)
            else:
                self.node.accept(block, "RECEIVED")
        elif kind == "get_chain":
            head = binary(message["head"], 32)
            if head not in store.blocks:
                raise ValueError("requested chain head is unknown")
            values = message["locator"]
            if type(values) is not list or not 1 <= len(values) <= 64:
                raise ValueError("locator must contain between 1 and 64 hashes")
            locator = [binary(value, 32) for value in values]
            blocks = store.segment(head, locator, BATCH_SIZE)
            self.send({"type": "chain", "head": head.hex(),
                       "headers": [block.to_bytes().hex() for block in blocks]})
        elif kind == "chain":
            head = binary(message["head"], 32)
            if self.sync_head is None or head != self.sync_head:
                raise ValueError("unsolicited chain response")
            headers = message["headers"]
            if type(headers) is not list or not 1 <= len(headers) <= BATCH_SIZE:
                raise ValueError("chain response must contain between 1 and 32 blocks")
            previous = None
            for header in headers:
                block = Block.from_bytes(binary(header, HEADER.size))
                if previous is None:
                    if block.previous_hash not in self.request_locator:
                        raise ValueError("chain response does not extend the requested locator")
                elif block.previous_hash != previous.hash:
                    raise ValueError("chain response is not ordered")
                self.node.accept(block, "SYNC")
                previous = block
            if head in store.blocks:
                self.sync_head = None
                print(f"SYNC_DONE height={store.tip.height} head={store.tip.hash.hex()}", flush=True)
                if self.next_head is not None:
                    next_head, self.next_head = self.next_head, None
                    self.sync(next_head)
            else:
                if previous.hash in self.request_locator:
                    raise ValueError("chain response made no progress")
                self.request(store.locator(previous.hash))
        else:
            raise ValueError("hello is only allowed during handshake")


class NetworkNode:
    def __init__(self, store: BlockStore, listen: tuple[str, int], peers: list[tuple[str, int]]) -> None:
        self.store, self.listen, self.peers = store, listen, peers
        self.sessions: set[Session] = set()
        self.ready = asyncio.Event()

    def accept(self, block: Block, source: str) -> bool:
        old_tip = self.store.tip
        if not self.store.accept(block):
            return False
        print(f"{source} block_height={block.height} height={self.store.tip.height} "
              f"accepted_block_count={self.store.accepted_block_count} "
              f"head={self.store.tip.hash.hex()}", flush=True)
        if block.previous_hash != old_tip.hash and self.store.tip.hash != old_tip.hash:
            print(f"REORG old_head={old_tip.hash.hex()} head={self.store.tip.hash.hex()}", flush=True)
        for session in tuple(self.sessions):
            session.send({"type": "block", "header": block.to_bytes().hex()})
            if self.store.tip.hash != old_tip.hash:
                session.send({"type": "head", "hash": self.store.tip.hash.hex()})
        return True

    async def connection(self, reader, writer) -> None:
        try:
            await Session(self, reader, writer).run()
        except (OSError, ValueError, asyncio.TimeoutError) as error:
            print(f"PEER_DISCONNECTED reason={error}", flush=True)

    async def connect(self, peer: tuple[str, int]) -> None:
        while True:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(*peer, limit=MAX_MESSAGE), timeout=5,
                )
            except (OSError, asyncio.TimeoutError) as error:
                print(f"PEER_UNAVAILABLE address={peer[0]}:{peer[1]} reason={error}", flush=True)
            else:
                await self.connection(reader, writer)
            await asyncio.sleep(1)

    async def compute(self, count: int) -> None:
        completed = 0
        while completed < count:
            parent = self.store.tip
            candidate = Block(
                self.store.config.version, self.store.config.network_id, parent.hash,
                parent.height + 1, self.store.node_id, self.store.config.target, 0,
            )
            started = perf_counter()
            for start in range(0, MAX_NONCE + 1, 4096):
                block = search_nonces(candidate, start, min(start + 4096, MAX_NONCE + 1))
                await asyncio.sleep(0)
                if self.store.tip.hash != parent.hash:
                    break
                if block is not None:
                    elapsed = perf_counter() - started
                    self.accept(block, "COMPUTED")
                    print(f"COMPUTE_RESULT nonce={block.nonce} attempts={block.nonce + 1} "
                          f"compute_seconds={elapsed:.6f}", flush=True)
                    completed += 1
                    break
            else:
                raise RuntimeError("nonce space exhausted without a valid result")
        print(f"COMPUTE_DONE local_blocks={completed} height={self.store.tip.height} "
              f"head={self.store.tip.hash.hex()}", flush=True)

    async def run(self, blocks: int) -> None:
        tasks = asyncio.TaskGroup()

        def incoming(reader, writer):
            tasks.create_task(self.connection(reader, writer))

        server = await asyncio.start_server(
            incoming, *self.listen, limit=MAX_MESSAGE, start_serving=False,
        )
        async with tasks:
            async with server:
                await server.start_serving()
                self.listen = server.sockets[0].getsockname()[:2]
                print(f"LISTEN address={self.listen[0]}:{self.listen[1]}", flush=True)
                for peer in self.peers:
                    tasks.create_task(self.connect(peer))
                tasks.create_task(self.compute(blocks))
                self.ready.set()
                await server.serve_forever()
