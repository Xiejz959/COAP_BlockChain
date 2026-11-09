from pathlib import Path
import tempfile
import unittest
import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from blocknode.chain.block import MAX_TARGET
from blocknode.chain.config import NetworkConfig
from blocknode.compute.pow import compute_block
from blocknode.network.node import NetworkNode
from blocknode.monitoring.dashboard import DashboardServer
from blocknode.storage.sqlite import BlockStore


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        config = NetworkConfig(1, b'coap-edu-pow-001', MAX_TARGET, 0)
        self.store = BlockStore(Path(self.directory.name), config)
        self.addCleanup(self.store.close)
        self.node = NetworkNode(self.store, ('127.0.0.1', 9001), [])
        self.server = DashboardServer(('127.0.0.1', 0))
        self.server.publish(self.node.observation.snapshot(self.node))
        self.server.start()
        self.addCleanup(self.server.close)
        self.url = f'http://127.0.0.1:{self.server.server.server_address[1]}'

    def test_snapshot_distinguishes_canonical_blocks_from_branches(self):
        genesis = self.store.tip
        a = compute_block(genesis, self.store.config, bytes.fromhex('11'*16)).block
        b = compute_block(genesis, self.store.config, bytes.fromhex('22'*16)).block
        self.node.accept(a, 'COMPUTED')
        self.node.accept(b, 'RECEIVED')
        self.server.publish(self.node.observation.snapshot(self.node))
        with urlopen(self.url+'/api/state') as response:
            state = json.load(response)
        self.assertEqual(state['height'], 1)
        self.assertEqual(state['known_blocks'], 3)
        self.assertEqual(state['side_blocks'], 1)
        self.assertEqual(state['head'], a.hash.hex())
        self.assertEqual(state['events'][0]['block_hash'], b.hash.hex())
        self.assertEqual(sum(item['canonical'] for item in state['blocks']), 2)
        self.assertIsNone(state['last_rate'])
        self.assertEqual(state['samples'], [])

    def test_assets_are_local_and_http_api_is_read_only(self):
        for route in ['/', '/style.css', '/app.js']:
            with urlopen(self.url+route) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
                self.assertGreater(len(response.read()), 100)
        for route, method, status in [('/../../main.tex','GET',404),('/api/state','POST',501)]:
            with self.assertRaises(HTTPError) as raised:
                urlopen(Request(self.url+route, method=method))
            self.assertEqual(raised.exception.code, status)
            raised.exception.close()
        self.assertEqual(self.store.accepted_block_count, 0)

    def test_computation_samples_and_events_use_actual_measurements(self):
        self.node.observation.computation(1000, 0.25)
        self.node.observation.record('SYNC_DONE','height 3')
        self.server.publish(self.node.observation.snapshot(self.node))
        with urlopen(self.url+'/api/state') as response:
            state=json.load(response)
        self.assertEqual(state['last_rate'], 4000)
        self.assertEqual(state['samples'][-1]['rate'], 4000)
        self.assertEqual(state['events'][0]['kind'], 'SYNC_DONE')
        self.assertEqual(state['local_blocks'], 1)


if __name__ == '__main__':
    unittest.main()
