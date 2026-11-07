from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'genesis.json'


class CLITests(unittest.TestCase):
    def invoke(self, directory, *options):
        return subprocess.run(
            [sys.executable, '-m', 'blocknode', '--config', str(CONFIG_PATH),
             '--data-dir', str(directory), *options],
            capture_output=True, text=True, timeout=30,
        )

    def test_three_blocks_restart_two_blocks_and_read_only_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first = self.invoke(path, '--blocks', '3')
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn('START height=0 accepted_block_count=0', first.stdout)
            self.assertIn('STOP height=3 accepted_block_count=3', first.stdout)
            first_head = first.stdout.splitlines()[-1].split('head=')[1]
            second = self.invoke(path, '--blocks', '2')
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn(f'START height=3 accepted_block_count=3 head={first_head}', second.stdout)
            self.assertIn('STOP height=5 accepted_block_count=5', second.stdout)
            status = self.invoke(path)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn('START height=5 accepted_block_count=5', status.stdout)
            self.assertNotIn('BLOCK height=', status.stdout)
            with sqlite3.connect(path / 'chain.sqlite3') as database:
                self.assertEqual(database.execute('SELECT COUNT(*) FROM blocks').fetchone()[0], 6)

    def test_negative_block_count_does_not_create_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'node'
            result = self.invoke(path, '--blocks', '-1')
            self.assertEqual(result.returncode, 2)
            self.assertFalse(path.exists())

    def test_existing_invalid_database_is_reported_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            original = b'not a SQLite database'
            (path / 'chain.sqlite3').write_bytes(original)
            result = self.invoke(path, '--blocks', '1')
            self.assertEqual(result.returncode, 1)
            self.assertIn('error:', result.stderr)
            self.assertEqual((path / 'chain.sqlite3').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
