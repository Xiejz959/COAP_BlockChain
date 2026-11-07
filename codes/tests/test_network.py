import asyncio
from contextlib import suppress
import json
from pathlib import Path
import tempfile
import unittest

from blocknode.chain.block import MAX_TARGET
from blocknode.chain.config import NetworkConfig
from blocknode.compute.pow import compute_block
from blocknode.network.node import NetworkNode
from blocknode.network.protocol import MAX_MESSAGE, endpoint, encode_message, read_message
from blocknode.storage.sqlite import BlockStore


class ProtocolTests(unittest.TestCase):
    def test_only_loopback_and_private_ipv4_endpoints_are_allowed(self):
        for value in ['127.0.0.1:9001', '192.168.8.10:9001', '10.0.0.1:9001']:
            self.assertEqual(endpoint(value)[1], 9001)
        for value in ['0.0.0.0:9001', '8.8.8.8:9001', 'example.com:9001', '127.0.0.1:0']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                endpoint(value)


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = NetworkConfig(1, b'coap-edu-pow-001', MAX_TARGET, 0)
        self.stores = []
        self.tasks = []

    async def asyncTearDown(self):
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with suppress(asyncio.CancelledError):
                await task
        for store in self.stores:
            store.close()
        self.directory.cleanup()

    def store(self, name):
        store = BlockStore(Path(self.directory.name) / name, self.config)
        self.stores.append(store)
        return store

    async def start(self, store, peers=(), listen=('127.0.0.1', 0)):
        node = NetworkNode(store, listen, list(peers))
        task = asyncio.create_task(node.run(0))
        self.tasks.append(task)
        await asyncio.wait_for(node.ready.wait(), timeout=5)
        return node, task

    async def until(self, condition):
        async with asyncio.timeout(6):
            while not condition():
                for task in self.tasks:
                    if task.done() and not task.cancelled():
                        task.result()
                await asyncio.sleep(0.01)

    async def test_live_broadcast_and_equal_chain_heads(self):
        a, _ = await self.start(self.store('a'))
        b, _ = await self.start(self.store('b'), [a.listen])
        await self.until(lambda: a.sessions and b.sessions)
        await a.compute(3)
        await self.until(lambda: b.store.tip.hash == a.store.tip.hash)
        self.assertEqual(b.store.accepted_block_count, 3)

    async def test_late_join_downloads_more_than_one_batch(self):
        source = self.store('source')
        for _ in range(75):
            source.accept(compute_block(source.tip, self.config, source.node_id).block)
        a, _ = await self.start(source)
        b, _ = await self.start(self.store('joining'), [a.listen])
        await self.until(lambda: b.store.tip.hash == a.store.tip.hash)
        self.assertEqual(b.store.accepted_block_count, 75)

    async def test_equal_forks_converge_after_one_branch_is_extended(self):
        left, right = self.store('left'), self.store('right')
        for store in [left, right]:
            for _ in range(2):
                store.accept(compute_block(store.tip, self.config, store.node_id).block)
        left_tip, right_tip = left.tip, right.tip
        a, _ = await self.start(left)
        b, _ = await self.start(right, [a.listen])
        await self.until(lambda: right_tip.hash in left.blocks and left_tip.hash in right.blocks)
        self.assertEqual(left.tip, left_tip)
        self.assertEqual(right.tip, right_tip)
        await b.compute(1)
        await self.until(lambda: left.tip == right.tip)
        self.assertEqual(left.accepted_block_count, 3)

    async def test_peer_reconnects_after_server_restart_and_catches_up(self):
        a, task = await self.start(self.store('a'))
        b, _ = await self.start(self.store('b'), [a.listen])
        await self.until(lambda: a.sessions and b.sessions)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await self.until(lambda: not b.sessions)
        for _ in range(4):
            a.store.accept(compute_block(a.store.tip, self.config, a.store.node_id).block)
        resumed, _ = await self.start(a.store, listen=a.listen)
        await self.until(lambda: b.store.tip == resumed.store.tip)
        self.assertEqual(b.store.accepted_block_count, 4)

    async def test_incompatible_genesis_is_rejected_without_losing_healthy_peer(self):
        a, _ = await self.start(self.store('a'))
        b, _ = await self.start(self.store('b'), [a.listen])
        await self.until(lambda: a.sessions and b.sessions)
        reader, writer = await asyncio.open_connection(*a.listen, limit=MAX_MESSAGE)
        try:
            hello = await read_message(reader)
            hello['node_id'] = '22' * 16
            hello['genesis'] = 'ff' * 32
            writer.write(encode_message(hello))
            await writer.drain()
            self.assertEqual(await asyncio.wait_for(reader.read(), timeout=3), b'')
            self.assertEqual(len(a.sessions), 1)
            await a.compute(1)
            await self.until(lambda: b.store.tip == a.store.tip)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_unknown_message_is_rejected(self):
        reader = asyncio.StreamReader(limit=MAX_MESSAGE)
        reader.feed_data(json.dumps({'type': 'unknown'}).encode() + b'\n')
        with self.assertRaisesRegex(ValueError, 'unknown message'):
            await read_message(reader)


if __name__ == '__main__':
    unittest.main()
