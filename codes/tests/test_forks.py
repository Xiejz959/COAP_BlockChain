from pathlib import Path
import sqlite3
import tempfile
import unittest

from blocknode.chain.block import MAX_TARGET
from blocknode.chain.config import NetworkConfig
from blocknode.compute.pow import compute_block
from blocknode.storage.sqlite import BlockStore


class ForkTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = NetworkConfig(1, b"coap-edu-pow-001", MAX_TARGET, 0)
        self.path = Path(self.directory.name)

    def store(self, name):
        store = BlockStore(self.path / name, self.config)
        self.addCleanup(store.close)
        return store

    def append(self, store, count):
        for _ in range(count):
            store.accept(compute_block(store.tip, self.config, store.node_id).block)

    def test_tie_retains_tip_longer_branch_replaces_canonical_and_survives_restart(self):
        a, b = self.store('a'), self.store('b')
        self.append(a, 2)
        self.append(b, 2)
        old_tip = a.tip
        for block in b.path_to(b.tip.hash)[1:]:
            self.assertTrue(a.accept(block))
        self.assertEqual(a.tip, old_tip)
        self.append(b, 1)
        a.accept(b.tip)
        self.assertEqual(a.tip, b.tip)
        self.assertEqual(a.accepted_block_count, 3)
        self.assertEqual(a.connection.execute('SELECT COUNT(*) FROM blocks').fetchone()[0], 4)
        self.assertEqual(len(a.blocks), 6)
        resumed = self.store('a')
        self.assertEqual(resumed.tip, b.tip)
        self.assertEqual(len(resumed.blocks), 6)

    def test_sync_locator_and_page_follow_requested_branch(self):
        a, b = self.store('a'), self.store('b')
        self.append(a, 70)
        cursor = None
        sizes = []
        while a.tip.hash not in b.blocks:
            page = a.segment(a.tip.hash, b.locator(cursor), 32)
            sizes.append(len(page))
            for block in page:
                b.accept(block)
            cursor = page[-1].hash
        self.assertEqual(sizes, [32, 32, 6])
        self.assertEqual(a.tip, b.tip)

    def test_legacy_single_chain_schema_is_preserved_on_upgrade(self):
        path = self.path / 'legacy'
        path.mkdir()
        genesis = self.config.genesis()
        node_id = bytes.fromhex('11111111111111111111111111111111')
        with sqlite3.connect(path / 'chain.sqlite3') as database:
            database.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY, value BLOB NOT NULL)')
            database.execute('CREATE TABLE blocks (height INTEGER PRIMARY KEY, header BLOB NOT NULL, hash BLOB NOT NULL UNIQUE)')
            database.execute('INSERT INTO metadata VALUES (?, ?)', ('node_id', node_id))
            database.execute('INSERT INTO blocks VALUES (?, ?, ?)', (0, genesis.to_bytes(), genesis.hash))
        store = self.store('legacy')
        self.assertEqual(store.node_id, node_id)
        self.assertEqual(store.tip, genesis)
        self.assertEqual(store.connection.execute('PRAGMA user_version').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
