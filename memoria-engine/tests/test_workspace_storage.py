from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.workspace_storage import LocalWorkspaceStorage  # noqa: E402


ROOT_DIR = Path(__file__).resolve().parents[1]


@contextmanager
def temp_workspace():
    base_dir = ROOT_DIR / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"workspace-storage-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class LocalWorkspaceStorageTests(unittest.TestCase):
    def test_reads_writes_lists_and_stats_relative_paths(self) -> None:
        with temp_workspace() as tmp_dir:
            storage = LocalWorkspaceStorage(tmp_dir)

            storage.mkdir("docs")
            storage.write_bytes("docs/readme.txt", b"hello")

            self.assertTrue(storage.exists("docs"))
            self.assertEqual(storage.read_bytes("docs/readme.txt"), b"hello")
            file_stat = storage.stat("docs/readme.txt")
            self.assertTrue(file_stat.exists)
            self.assertTrue(file_stat.is_file)
            self.assertFalse(file_stat.is_dir)
            self.assertEqual(file_stat.size, 5)
            self.assertEqual(file_stat.path, "docs/readme.txt")

            entries = storage.list_dir("docs")

            self.assertEqual([entry.name for entry in entries], ["readme.txt"])
            self.assertEqual(entries[0].path, "docs/readme.txt")
            self.assertTrue(entries[0].is_file)
            self.assertFalse(entries[0].is_dir)
            self.assertEqual(entries[0].size, 5)

    def test_list_dir_returns_directory_entries_without_size(self) -> None:
        with temp_workspace() as tmp_dir:
            storage = LocalWorkspaceStorage(tmp_dir)

            storage.mkdir("docs/nested")
            storage.write_bytes("docs/readme.txt", b"hello")

            entries = storage.list_dir("docs")

            self.assertEqual([entry.name for entry in entries], ["nested", "readme.txt"])
            directory_entry = entries[0]
            self.assertEqual(directory_entry.path, "docs/nested")
            self.assertTrue(directory_entry.is_dir)
            self.assertFalse(directory_entry.is_file)
            self.assertIsNone(directory_entry.size)

    def test_missing_paths_return_non_existing_stat_and_empty_listing(self) -> None:
        with temp_workspace() as tmp_dir:
            storage = LocalWorkspaceStorage(tmp_dir)

            missing = storage.stat("missing")

            self.assertFalse(missing.exists)
            self.assertFalse(missing.is_file)
            self.assertFalse(missing.is_dir)
            self.assertEqual(storage.list_dir("missing"), ())

    def test_accepts_absolute_paths_inside_workspace_root(self) -> None:
        with temp_workspace() as tmp_dir:
            storage = LocalWorkspaceStorage(tmp_dir)
            absolute_file = tmp_dir / "docs" / "absolute.txt"

            storage.write_bytes(absolute_file, b"absolute")

            self.assertTrue(storage.exists(absolute_file))
            self.assertEqual(storage.read_bytes("docs/absolute.txt"), b"absolute")
            self.assertEqual(storage.stat(absolute_file).path, "docs/absolute.txt")

    def test_rejects_absolute_paths_outside_workspace_root(self) -> None:
        with temp_workspace() as tmp_dir:
            storage = LocalWorkspaceStorage(tmp_dir)
            outside_file = tmp_dir.parent / f"outside-{uuid.uuid4().hex}.txt"

            with self.assertRaises(ValueError):
                storage.write_bytes(outside_file, b"outside")

            self.assertFalse(outside_file.exists())

    def test_rejects_paths_that_escape_workspace_root(self) -> None:
        with temp_workspace() as tmp_dir:
            storage = LocalWorkspaceStorage(tmp_dir)

            with self.assertRaises(ValueError):
                storage.write_bytes("../escape.txt", b"escape")

            self.assertFalse((tmp_dir.parent / "escape.txt").exists())


if __name__ == "__main__":
    unittest.main()
