from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.historical_map_catalog import (  # noqa: E402
    build_historical_map_catalog,
    render_historical_map_catalog_markdown,
)
from caduti_fonti_report.document_analysis.input_processing_plan import build_input_processing_plan  # noqa: E402


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


def write_binary(path: Path, value: bytes = b"test-bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


class HistoricalMapCatalogTests(unittest.TestCase):
    def test_catalog_keeps_only_historical_map_candidates(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            map_path = root_dir / "mappe" / "carta-operativa-1944.jpg"
            write_binary(map_path, b"map-bytes")
            write_binary(root_dir / "foto" / "scansione.jpg", b"photo-bytes")
            output_json = tmp_dir / "historical_map_catalog.json"
            output_md = tmp_dir / "historical_map_catalog.md"

            catalog = build_historical_map_catalog(root_dir=root_dir, output_json=output_json, output_md=output_md)
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(catalog["@type"], "HistoricalMapCatalog")
        self.assertEqual(persisted["map_candidate_count"], 1)
        candidate = persisted["maps"][0]
        self.assertEqual(candidate["@type"], "HistoricalMapCandidate")
        self.assertTrue(candidate["raw_file"].endswith("carta-operativa-1944.jpg"))
        self.assertEqual(candidate["sha256"], hashlib.sha256(b"map-bytes").hexdigest())
        self.assertEqual(candidate["georeferencing_status"], "not_georeferenced")
        self.assertEqual(candidate["map_ocr_status"], "not_extracted")
        self.assertEqual(candidate["review_status"], "unreviewed")
        self.assertIn("carta", candidate["map_signal_terms"])
        self.assertIn("Historical map catalog", markdown)
        self.assertIn("not_georeferenced", markdown)
        self.assertNotIn("EvidenceClaim", json.dumps(persisted))
        self.assertNotIn("ProfilePatch", json.dumps(persisted))
        self.assertNotIn("verified_facts", json.dumps(persisted))

    def test_catalog_can_reuse_existing_input_plan_json(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            write_binary(root_dir / "karte" / "lagekarte-1944.png")
            input_plan_json = tmp_dir / "input_processing_plan.json"
            build_input_processing_plan(root_dir=root_dir, output_json=input_plan_json)

            catalog = build_historical_map_catalog(input_plan_json=input_plan_json)

        self.assertEqual(catalog["map_candidate_count"], 1)
        self.assertEqual(catalog["maps"][0]["recommended_action"], "historical_map_georeferencing_required")
        self.assertIn("karte", catalog["maps"][0]["map_signal_terms"])

    def test_markdown_renderer_handles_empty_catalog(self) -> None:
        markdown = render_historical_map_catalog_markdown(
            {
                "root_dir": "data/raw",
                "map_candidate_count": 0,
                "review_status": "unreviewed",
                "maps": [],
            }
        )

        self.assertIn("Nessuna mappa candidata", markdown)
        self.assertIn("Mappe candidate: `0`", markdown)


if __name__ == "__main__":
    unittest.main()
