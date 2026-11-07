from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from blocknode.chain.block import MAX_TARGET, ZERO_HASH
from blocknode.chain.config import NetworkConfig
from blocknode.compute.pow import compute_block
from blocknode.storage.sqlite import BlockStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.config = NetworkConfig(1, b"coap-edu-pow-001", MAX_TARGET, 0)

    def test_restart_preserves_tip_identity_and_count(self):
        store = BlockStore(self.path, self.config)
        self.assertEqual(store.accepted_block_count, 0)
        for _ in range(3):
            store.accept(compute_block(store.tip, self.config, store.node_id).block)
        tip, node_id = store.tip, store.node_id
        store.close()
        resumed = BlockStore(self.path, self.config)
        self.addCleanup(resumed.close)
        self.assertEqual(resumed.tip, tip)
        self.assertEqual(resumed.node_id, node_id)
        self.assertEqual(resumed.accepted_block_count, 3)
        for _ in range(2):
            resumed.accept(compute_block(resumed.tip, self.config, resumed.node_id).block)
        self.assertEqual(resumed.accepted_block_count, 5)
        self.assertEqual(resumed.connection.execute('SELECT COUNT(*) FROM blocks').fetchone()[0], 6)

    def test_repeated_blocks_and_genesis_do_not_increase_count(self):
        store = BlockStore(self.path, self.config)
        self.addCleanup(store.close)
        genesis = store.tip
        block = compute_block(store.tip, self.config, store.node_id).block
        self.assertTrue(store.accept(block))
        self.assertFalse(store.accept(block))
        self.assertFalse(store.accept(genesis))
        self.assertEqual(store.accepted_block_count, 1)

    def test_rejected_block_does_not_change_memory_or_database(self):
        store = BlockStore(self.path, self.config)
        self.addCleanup(store.close)
        block = compute_block(store.tip, self.config, store.node_id).block
        with self.assertRaisesRegex(ValueError, 'previous_hash'):
            store.accept(replace(block, previous_hash=ZERO_HASH))
        self.assertEqual(store.accepted_block_count, 0)
        self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM blocks').fetchone()[0], 1)

    def test_existing_chain_rejects_changed_configuration(self):
        store = BlockStore(self.path, self.config)
        store.close()
        changed = replace(self.config, network_id=b'another-network!')
        with self.assertRaisesRegex(ValueError, 'genesis'):
            BlockStore(self.path, changed)
        original = BlockStore(self.path, self.config)
        self.addCleanup(original.close)
        self.assertEqual(original.accepted_block_count, 0)

    def test_tampered_header_is_rejected_on_restart(self):
        store = BlockStore(self.path, self.config)
        block = compute_block(store.tip, self.config, store.node_id).block
        store.accept(block)
        with store.connection:
            store.connection.execute(
                'UPDATE blocks SET header = ? WHERE height = 1',
                (replace(block, nonce=block.nonce + 1).to_bytes(),),
            )
        store.close()
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            BlockStore(self.path, self.config)

    def test_missing_genesis_is_not_recreated(self):
        store = BlockStore(self.path, self.config)
        with store.connection:
            store.connection.execute('DELETE FROM blocks')
        store.close()
        with self.assertRaisesRegex(ValueError, 'no genesis'):
            BlockStore(self.path, self.config)
        with sqlite3.connect(self.path / 'chain.sqlite3') as database:
            self.assertEqual(database.execute('SELECT COUNT(*) FROM blocks').fetchone()[0], 0)

    def test_gaps_in_persisted_chain_are_rejected(self):
        store = BlockStore(self.path, self.config)
        for _ in range(2):
            store.accept(compute_block(store.tip, self.config, store.node_id).block)
        with store.connection:
            store.connection.execute('DELETE FROM blocks WHERE height = 1')
        store.close()
        with self.assertRaisesRegex(ValueError, 'height'):
            BlockStore(self.path, self.config)


if __name__ == '__main__':
    unittest.main()
