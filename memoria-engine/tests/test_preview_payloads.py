from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.preview_payloads import (  # noqa: E402
    dict_object,
    list_items,
    list_strings,
    load_json_object,
    load_optional_json_object,
    unique_non_empty,
    write_json,
    write_markdown,
    yaml_value,
)


@contextmanager
def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class PreviewPayloadsTests(unittest.TestCase):
    def test_load_json_object_keeps_only_object_payloads(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            object_path = tmp_dir / "payload.json"
            list_path = tmp_dir / "list.json"
            object_path.write_text(json.dumps({"review_status": "preview-only"}), encoding="utf-8")
            list_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

            self.assertEqual(load_json_object(object_path), {"review_status": "preview-only"})
            self.assertEqual(load_json_object(list_path), {})

    def test_load_optional_json_object_is_conservative(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            object_path = tmp_dir / "payload.json"
            list_path = tmp_dir / "list.json"
            invalid_path = tmp_dir / "invalid.json"
            missing_path = tmp_dir / "missing.json"
            object_path.write_text(json.dumps({"status": "preview-only"}), encoding="utf-8")
            list_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
            invalid_path.write_text("{not json", encoding="utf-8")

            self.assertEqual(load_optional_json_object(object_path), {"status": "preview-only"})
            self.assertEqual(load_optional_json_object(list_path), {})
            self.assertEqual(load_optional_json_object(invalid_path), {})
            self.assertEqual(load_optional_json_object(missing_path), {})
            self.assertEqual(load_optional_json_object(None), {})

    def test_coercion_helpers_are_conservative(self) -> None:
        self.assertEqual(dict_object({"a": 1}), {"a": 1})
        self.assertEqual(dict_object(["a"]), {})
        self.assertEqual(list_items([{"a": 1}, "skip", {"b": 2}]), [{"a": 1}, {"b": 2}])
        self.assertEqual(list_items({"a": 1}), [])
        self.assertEqual(list_strings(" value "), [" value "])
        self.assertEqual(list_strings(["a", "", 2]), ["a", "2"])
        self.assertEqual(unique_non_empty([" a ", "b", "a", "", "b"]), ["a", "b"])
        self.assertEqual(yaml_value('a "quoted" value'), '"a \\"quoted\\" value"')

    def test_write_helpers_create_parent_dirs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            json_path = tmp_dir / "nested" / "payload.json"
            markdown_path = tmp_dir / "nested" / "payload.md"

            write_json(json_path, {"preview_only": True})
            write_markdown(markdown_path, "# Preview\n")

            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), {"preview_only": True})
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# Preview\n")


if __name__ == "__main__":
    unittest.main()
