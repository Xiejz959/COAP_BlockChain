"""Validated block graph and transactionally selected canonical chain."""

from pathlib import Path
import sqlite3
from uuid import uuid4

from blocknode.chain.block import Block, GENESIS_NODE_ID
from blocknode.chain.config import NetworkConfig
from blocknode.chain.validation import validate_block


class BlockStore:
    def __init__(self, data_dir: Path, config: NetworkConfig) -> None:
        self.config = config
        genesis = config.genesis()
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / "chain.sqlite3"
        is_new = not path.exists()
        self.connection = sqlite3.connect(path)
        try:
            if is_new:
                with self.connection:
                    self.connection.execute(
                        "CREATE TABLE metadata (key TEXT PRIMARY KEY, value BLOB NOT NULL)"
                    )
                    self.connection.execute(
                        "CREATE TABLE blocks (height INTEGER PRIMARY KEY, "
                        "header BLOB NOT NULL, hash BLOB NOT NULL UNIQUE)"
                    )
                    self.connection.execute(
                        "INSERT INTO metadata VALUES (?, ?)", ("node_id", uuid4().bytes),
                    )
                    self.connection.execute(
                        "INSERT INTO blocks VALUES (?, ?, ?)",
                        (0, genesis.to_bytes(), genesis.hash),
                    )
            row = self.connection.execute(
                "SELECT value FROM metadata WHERE key = ?", ("node_id",),
            ).fetchone()
            if row is None or type(row[0]) is not bytes or len(row[0]) != 16:
                raise ValueError("stored node ID is missing or invalid")
            self.node_id = row[0]
            if self.node_id == GENESIS_NODE_ID:
                raise ValueError("stored node ID cannot be the genesis node ID")
            self.tip = self._load_chain(genesis)
            self._load_graph(genesis)
        except (ValueError, sqlite3.Error):
            self.connection.close()
            raise

    def _load_chain(self, genesis: Block) -> Block:
        parent = None
        for height, header, stored_hash in self.connection.execute(
            "SELECT height, header, hash FROM blocks ORDER BY height"
        ):
            if type(header) is not bytes or type(stored_hash) is not bytes:
                raise ValueError("stored block must contain binary header and hash")
            block = Block.from_bytes(header)
            if height != block.height or stored_hash != block.hash:
                raise ValueError("stored block height or hash is inconsistent")
            if parent is None:
                if block != genesis:
                    raise ValueError("stored genesis does not match configuration")
            else:
                validate_block(block, parent, self.config)
            parent = block
        if parent is None:
            raise ValueError("stored chain has no genesis block")
        return parent

    @property
    def accepted_block_count(self) -> int:
        return self.tip.height

    def _load_graph(self, genesis: Block) -> None:
        schema_version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if schema_version == 0:
            # Additive schema upgrade: preserve the already validated single-node chain.
            with self.connection:
                self.connection.execute("BEGIN")
                self.connection.execute(
                    "CREATE TABLE block_graph (hash BLOB PRIMARY KEY, header BLOB NOT NULL)"
                )
                self.connection.execute("INSERT INTO block_graph SELECT hash, header FROM blocks")
                self.connection.execute("PRAGMA user_version = 1")
        elif schema_version != 1:
            raise ValueError("unsupported database schema version")
        decoded = []
        for digest, header in self.connection.execute("SELECT hash, header FROM block_graph"):
            if type(header) is not bytes or type(digest) is not bytes:
                raise ValueError("stored graph block must contain binary header and hash")
            block = Block.from_bytes(header)
            if block.hash != digest:
                raise ValueError("stored graph hash is inconsistent")
            decoded.append(block)
        self.blocks: dict[bytes, Block] = {}
        self.work: dict[bytes, int] = {}
        self.block_work = (1 << 256) // (self.config.target + 1)
        for block in sorted(decoded, key=lambda item: item.height):
            if block.height == 0:
                if block != genesis:
                    raise ValueError("stored graph genesis does not match configuration")
                work = 0
            else:
                parent = self.blocks.get(block.previous_hash)
                if parent is None:
                    raise ValueError("stored graph has an unknown parent")
                validate_block(block, parent, self.config)
                work = self.work[parent.hash] + self.block_work
            self.blocks[block.hash] = block
            self.work[block.hash] = work
        if self.tip.hash not in self.blocks:
            raise ValueError("canonical chain is missing from block graph")
        if any(work > self.work[self.tip.hash] for work in self.work.values()):
            raise ValueError("stored canonical chain does not have maximum cumulative work")

    def path_to(self, digest: bytes) -> list[Block]:
        block = self.blocks[digest]
        path = [block]
        while block.height:
            block = self.blocks[block.previous_hash]
            path.append(block)
        path.reverse()
        return path

    def locator(self, start: bytes | None = None) -> list[bytes]:
        block = self.blocks[self.tip.hash if start is None else start]
        result = []
        step = 1
        while True:
            result.append(block.hash)
            if block.height == 0:
                return result
            for _ in range(min(step, block.height)):
                block = self.blocks[block.previous_hash]
            step *= 2

    def segment(self, head: bytes, locator: list[bytes], limit: int) -> list[Block]:
        path = self.path_to(head)
        positions = {block.hash: index for index, block in enumerate(path)}
        for digest in locator:
            if digest in positions:
                start = positions[digest] + 1
                return path[start:start + limit]
        raise ValueError("chain request has no common genesis")

    def accept(self, block: Block) -> bool:
        digest = block.hash
        if digest in self.blocks:
            return False
        parent = self.blocks.get(block.previous_hash)
        if parent is None:
            raise ValueError("unknown parent in previous_hash")
        validate_block(block, parent, self.config)
        work = self.work[parent.hash] + self.block_work
        selected = work > self.work[self.tip.hash]
        with self.connection:
            self.connection.execute(
                "INSERT INTO block_graph VALUES (?, ?)", (digest, block.to_bytes()),
            )
            if selected:
                path = self.path_to(parent.hash) + [block]
                self.connection.execute("DELETE FROM blocks")
                self.connection.executemany(
                    "INSERT INTO blocks VALUES (?, ?, ?)",
                    [(item.height, item.to_bytes(), item.hash) for item in path],
                )
        self.blocks[digest] = block
        self.work[digest] = work
        if selected:
            self.tip = block
        return True

    def close(self) -> None:
        self.connection.close()
