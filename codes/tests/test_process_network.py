from contextlib import closing
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest


CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'genesis.json'


class ProcessNetworkTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.launches = 0

    def port(self):
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0))
            return connection.getsockname()[1]

    def stop(self, process):
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            process.wait(timeout=5)
        self.assertEqual(process.returncode, 0)

    def launch(self, name, port, blocks, peer=None):
        self.launches += 1
        log = self.root / f'{name}-{self.launches}.log'
        output = log.open('w')
        self.addCleanup(output.close)
        command = [sys.executable, '-B', '-m', 'blocknode', '--config', str(CONFIG_PATH),
                   '--data-dir', str(self.root / name), '--listen', f'127.0.0.1:{port}',
                   '--blocks', str(blocks)]
        if peer is not None:
            command += ['--peer', f'127.0.0.1:{peer}']
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        self.addCleanup(self.stop, process)
        self.until(lambda: 'LISTEN address=' in log.read_text(), process, log)
        return process, log

    def until(self, condition, process, log):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if condition():
                return
            self.assertIsNone(process.poll(), log.read_text())
            time.sleep(0.02)
        self.fail(log.read_text())

    def tip(self, name):
        with closing(sqlite3.connect(self.root / name / 'chain.sqlite3')) as database:
            return database.execute('SELECT height, hash FROM blocks ORDER BY height DESC LIMIT 1').fetchone()

    def test_two_processes_sync_and_offline_peer_catches_up_on_restart(self):
        a_port, b_port = self.port(), self.port()
        a, a_log = self.launch('a', a_port, 3)
        self.until(lambda: 'COMPUTE_DONE local_blocks=3' in a_log.read_text(), a, a_log)
        b, b_log = self.launch('b', b_port, 0, peer=a_port)
        self.until(lambda: self.tip('b')[0] == 3, b, b_log)
        self.assertEqual(self.tip('a'), self.tip('b'))
        self.stop(b)
        self.stop(a)
        a, a_log = self.launch('a', a_port, 2)
        self.until(lambda: 'COMPUTE_DONE local_blocks=2' in a_log.read_text(), a, a_log)
        b, b_log = self.launch('b', b_port, 0, peer=a_port)
        self.until(lambda: self.tip('b')[0] == 5, b, b_log)
        self.assertEqual(self.tip('a'), self.tip('b'))
        self.assertIn('START height=3', b_log.read_text())
        self.assertIn('PEER_CONNECTED', b_log.read_text())


if __name__ == '__main__':
    unittest.main()
