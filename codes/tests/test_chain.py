from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from blocknode.chain.block import Block, HEADER, MAX_TARGET, ZERO_HASH
from blocknode.chain.config import NetworkConfig, load_config
from blocknode.chain.validation import validate_block
from blocknode.compute.pow import compute_block


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "genesis.json"
NODE_ID = bytes.fromhex("11111111111111111111111111111111")


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.config = NetworkConfig(1, b"coap-edu-pow-001", MAX_TARGET, 0)
        self.genesis = self.config.genesis()
        self.block = compute_block(self.genesis, self.config, NODE_ID).block

    def test_committed_genesis_matches_independent_encoding_vector(self):
        genesis = load_config(CONFIG_PATH).genesis()
        self.assertEqual(HEADER.size, 114)
        self.assertEqual(genesis.to_bytes()[:18], b"\x00\x01coap-edu-pow-001")
        self.assertEqual(genesis.to_bytes()[50:58], bytes(8))
        self.assertEqual(genesis.to_bytes()[-8:], (24452).to_bytes(8, "big"))
        self.assertEqual(
            genesis.hash.hex(),
            "0000afc5ce4192fbc256c769acc9bb16cc9010bb585056cc355b828c9deb65fc",
        )
        self.assertEqual(Block.from_bytes(genesis.to_bytes()), genesis)

    def test_reference_compute_result_satisfies_validation(self):
        config = load_config(CONFIG_PATH)
        result = compute_block(config.genesis(), config, NODE_ID)
        validate_block(result.block, config.genesis(), config)
        self.assertGreater(result.attempts, 0)
        self.assertEqual(result.attempts, result.block.nonce + 1)
        self.assertGreaterEqual(result.elapsed_seconds, 0)

    def test_wrong_parent_and_height_are_rejected(self):
        for change, message in [
            ({"previous_hash": ZERO_HASH}, "previous_hash"),
            ({"height": 3}, "height"),
        ]:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                validate_block(replace(self.block, **change), self.genesis, self.config)

    def test_wrong_network_version_target_and_reserved_node_are_rejected(self):
        for change in [
            {"network_id": b"another-network!"},
            {"version": 2},
            {"target": MAX_TARGET - 1},
            {"node_id": bytes(16)},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_block(replace(self.block, **change), self.genesis, self.config)

    def test_unsolved_pow_is_rejected(self):
        config = load_config(CONFIG_PATH)
        parent = config.genesis()
        block = Block(1, config.network_id, parent.hash, 1, NODE_ID, config.target, 0)
        while int.from_bytes(block.hash, "big") <= config.target:
            block = replace(block, nonce=block.nonce + 1)
        with self.assertRaisesRegex(ValueError, "PoW"):
            validate_block(block, parent, config)

    def test_header_bounds_and_length_are_checked(self):
        for change in [
            {"nonce": -1}, {"nonce": 1 << 64}, {"height": 1 << 63},
            {"node_id": bytes(15)}, {"height": True},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.block, **change)
        with self.assertRaisesRegex(ValueError, "114 bytes"):
            Block.from_bytes(self.block.to_bytes()[:-1])

    def test_invalid_genesis_and_malformed_configuration_are_rejected(self):
        config = load_config(CONFIG_PATH)
        invalid = replace(config, genesis_nonce=0)
        self.assertGreater(int.from_bytes(
            Block(1, config.network_id, ZERO_HASH, 0, bytes(16), config.target, 0).hash, "big"
        ), config.target)
        with self.assertRaisesRegex(ValueError, "genesis"):
            invalid.genesis()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{"version": 1}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "configuration"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
