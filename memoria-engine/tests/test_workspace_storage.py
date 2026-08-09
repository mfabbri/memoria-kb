from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.workspace_storage import LocalWorkspaceStorage, PCloudWorkspaceStorage  # noqa: E402


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


class PCloudWorkspaceStorageTests(unittest.TestCase):
    def test_lists_directory_with_root_folder_id_and_maps_entries_to_logical_paths(self) -> None:
        calls: list[tuple[str, dict[str, str], int]] = []

        def http_json_get(url: str, params: dict[str, str], timeout: int) -> dict[str, object]:
            calls.append((url, params, timeout))
            return {
                "result": 0,
                "metadata": {
                    "isfolder": True,
                    "path": "/MeMoRiA",
                    "contents": [
                        {"name": "database", "path": "/MeMoRiA/database", "isfolder": True, "folderid": 42},
                        {"name": "README.txt", "path": "/MeMoRiA/README.txt", "isfolder": False, "fileid": 7, "size": 12},
                    ],
                },
            }

        storage = PCloudWorkspaceStorage(
            access_token="secret-token",
            root="/MeMoRiA",
            root_folder_id="123",
            api_host="eapi.pcloud.com",
            http_json_get=http_json_get,
        )

        entries = storage.list_dir(".")

        self.assertEqual(calls[0][0], "https://eapi.pcloud.com/listfolder")
        self.assertEqual(calls[0][1]["folderid"], "123")
        self.assertNotIn("path", calls[0][1])
        self.assertEqual(calls[0][1]["access_token"], "secret-token")
        self.assertNotIn("auth", calls[0][1])
        self.assertEqual([entry.path for entry in entries], ["database", "README.txt"])
        self.assertTrue(entries[0].is_dir)
        self.assertEqual(entries[1].size, 12)

    def test_stats_file_by_remote_path(self) -> None:
        def http_json_get(url: str, params: dict[str, str], timeout: int) -> dict[str, object]:
            self.assertEqual(url, "https://api.pcloud.com/stat")
            self.assertEqual(params["path"], "/MeMoRiA/database/evidence.sqlite")
            return {
                "result": 0,
                "metadata": {
                    "path": "/MeMoRiA/database/evidence.sqlite",
                    "isfolder": False,
                    "size": 99,
                },
            }

        storage = PCloudWorkspaceStorage(access_token="secret-token", root="/MeMoRiA", http_json_get=http_json_get)

        file_stat = storage.stat("database/evidence.sqlite")

        self.assertTrue(file_stat.exists)
        self.assertTrue(file_stat.is_file)
        self.assertEqual(file_stat.path, "database/evidence.sqlite")
        self.assertEqual(file_stat.size, 99)

    def test_missing_directory_listing_returns_empty_tuple(self) -> None:
        def http_json_get(url: str, params: dict[str, str], timeout: int) -> dict[str, object]:
            return {"result": 2005}

        storage = PCloudWorkspaceStorage(access_token="secret-token", root="/MeMoRiA", http_json_get=http_json_get)

        self.assertEqual(storage.list_dir("missing"), ())

    def test_reads_file_through_getfilelink(self) -> None:
        json_calls: list[tuple[str, dict[str, str], int]] = []
        byte_calls: list[tuple[str, int]] = []

        def http_json_get(url: str, params: dict[str, str], timeout: int) -> dict[str, object]:
            json_calls.append((url, params, timeout))
            return {"result": 0, "hosts": ["c1.pcloud.com"], "path": "/hash/readme.txt"}

        def http_bytes_get(url: str, timeout: int) -> bytes:
            byte_calls.append((url, timeout))
            return b"hello"

        storage = PCloudWorkspaceStorage(
            access_token="secret-token",
            root="/MeMoRiA",
            timeout=5,
            http_json_get=http_json_get,
            http_bytes_get=http_bytes_get,
        )

        self.assertEqual(storage.read_bytes("README.txt"), b"hello")
        self.assertEqual(json_calls[0][0], "https://api.pcloud.com/getfilelink")
        self.assertEqual(json_calls[0][1]["path"], "/MeMoRiA/README.txt")
        self.assertEqual(byte_calls, [("https://c1.pcloud.com/hash/readme.txt", 5)])

    def test_rejects_writes_and_paths_that_escape_root(self) -> None:
        storage = PCloudWorkspaceStorage(access_token="secret-token", root="/MeMoRiA", http_json_get=lambda *_: {})

        with self.assertRaises(NotImplementedError):
            storage.write_bytes("diagnostics.txt", b"blocked")
        with self.assertRaises(NotImplementedError):
            storage.mkdir("diagnostics")
        with self.assertRaises(ValueError):
            storage.stat("../escape.txt")


if __name__ == "__main__":
    unittest.main()
