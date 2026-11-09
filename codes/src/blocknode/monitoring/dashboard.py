"""Standard-library HTTP serving immutable snapshots, never sharing SQLite threads."""

from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from time import time, monotonic


class Observation:
    def __init__(self):
        self.started = monotonic()
        self.events = deque(maxlen=100)
        self.samples = deque(maxlen=120)
        self.computing = False
        self.last_rate = None
        self.local_blocks = 0
        self.record('START', '节点已启动，已验证本地存储')

    def record(self, kind, detail, block_hash=None):
        self.events.append({'time': time(), 'kind': kind, 'detail': detail, 'block_hash': block_hash})

    def computation(self, attempts, duration):
        self.last_rate = attempts / duration
        self.samples.append({'time': time(), 'rate': self.last_rate})
        self.local_blocks += 1

    def snapshot(self, node):
        store = node.store
        canonical = {block.hash for block in store.path_to(store.tip.hash)}
        floor = max(0, store.tip.height - 19)
        blocks = [{
            'hash': block.hash.hex(), 'parent': block.previous_hash.hex(),
            'height': block.height, 'node_id': block.node_id.hex(),
            'nonce': str(block.nonce), 'canonical': block.hash in canonical,
            'work': str(store.work[block.hash]),
        } for block in sorted(store.blocks.values(), key=lambda item: (item.height, item.hash))
            if block.height >= floor]
        peers = []
        for session in node.sessions:
            head = session.remote_head
            known = store.blocks.get(head)
            peers.append({
                'node_id': session.peer_id.hex(), 'address': session.address,
                'head': head.hex(), 'height': known.height if known is not None else None,
                'syncing': session.sync_head is not None,
                'last_seen': session.last_seen,
            })
        return {
            'updated_at': time(), 'uptime': monotonic() - self.started,
            'node_id': store.node_id.hex(), 'network': store.config.network_id.decode('ascii'),
            'listen': f'{node.listen[0]}:{node.listen[1]}',
            'height': store.tip.height, 'head': store.tip.hash.hex(),
            'work': str(store.work[store.tip.hash]), 'target': f'{store.config.target:064x}',
            'known_blocks': len(store.blocks),
            'side_blocks': len(store.blocks) - len(canonical),
            'computing': self.computing, 'local_blocks': self.local_blocks,
            'last_rate': self.last_rate, 'samples': list(self.samples),
            'blocks': blocks, 'visible_from': floor,
            'peers': sorted(peers, key=lambda peer: peer['node_id']),
            'events': list(reversed(self.events)),
        }


class DashboardServer:
    def __init__(self, address):
        assets = Path(__file__).parent / 'web'

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/api/state':
                    body = self.server.snapshot
                    content_type = 'application/json; charset=utf-8'
                elif self.path in ['/', '/index.html', '/style.css', '/app.js']:
                    filename = 'index.html' if self.path == '/' else self.path[1:]
                    body = (assets / filename).read_bytes()
                    content_type = {'index.html': 'text/html; charset=utf-8',
                                    'style.css': 'text/css; charset=utf-8',
                                    'app.js': 'text/javascript; charset=utf-8'}[filename]
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(address, Handler)
        self.server.snapshot = b'{}'
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def publish(self, state):
        self.server.snapshot = json.dumps(state, ensure_ascii=False, allow_nan=False).encode('utf-8')

    def start(self):
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
