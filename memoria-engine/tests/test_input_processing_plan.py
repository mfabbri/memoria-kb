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

from caduti_fonti_report.document_analysis.input_processing_plan import (  # noqa: E402
    build_input_processing_plan,
    render_input_processing_plan_markdown,
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


def write_binary(path: Path, value: bytes = b"test-bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


class InputProcessingPlanTests(unittest.TestCase):
    def test_classifies_mixed_root_assets_without_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            (root_dir / "docs").mkdir(parents=True)
            (root_dir / "docs" / "scheda.txt").write_text("Scheda testuale", encoding="utf-8")
            (root_dir / "docs" / "pagina.html").write_text("<html>Pagina</html>", encoding="utf-8")
            (root_dir / "docs" / "caduti_purocielo.csv").write_text("nome,nascita\nAndreoli Dino,1920\n", encoding="utf-8")
            write_binary(root_dir / "docs" / "relazione.docx")
            write_binary(root_dir / "foto" / "scansione.jpg")
            write_binary(root_dir / "mappe" / "carta-operativa-1944.jpg")
            write_binary(root_dir / "pdf" / "fascicolo.pdf")
            write_binary(root_dir / "audio" / "intervista.wav")
            write_binary(root_dir / "video" / "filmato.mp4")
            write_binary(root_dir / "bin" / "dump.unknown")
            output_json = tmp_dir / "input_processing_plan.json"
            output_md = tmp_dir / "input_processing_plan.md"

            plan = build_input_processing_plan(root_dir=root_dir, output_json=output_json, output_md=output_md)
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(plan["@type"], "InputProcessingPlan")
        self.assertEqual(plan["asset_count"], 10)
        self.assertEqual(persisted["action_counts"]["text_document_ready"], 1)
        self.assertEqual(persisted["action_counts"]["html_document_ready"], 1)
        self.assertEqual(persisted["action_counts"]["tabular_document_ready"], 1)
        self.assertEqual(persisted["action_counts"]["word_document_ready"], 1)
        self.assertEqual(persisted["action_counts"]["image_ocr_required"], 1)
        self.assertEqual(persisted["action_counts"]["historical_map_georeferencing_required"], 1)
        self.assertEqual(persisted["action_counts"]["pdf_text_extraction_required"], 1)
        self.assertEqual(persisted["action_counts"]["audio_transcription_required"], 1)
        self.assertEqual(persisted["action_counts"]["video_transcription_required"], 1)
        self.assertEqual(persisted["action_counts"]["unsupported_media_type"], 1)
        self.assertIn("historical_map_ocr_required", json.dumps(persisted))
        self.assertIn("historical_map_georeferencing_required", markdown)
        self.assertNotIn("EvidenceClaim", json.dumps(persisted))
        self.assertNotIn("ProfilePatch", json.dumps(persisted))
        self.assertNotIn("verified_facts", json.dumps(persisted))

    def test_plan_preserves_inventory_provenance_and_hashes(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            raw_path = root_dir / "manual" / "nota.txt"
            raw_path.parent.mkdir(parents=True)
            raw_path.write_text("Nota con provenance", encoding="utf-8")

            plan = build_input_processing_plan(root_dir=root_dir)

        asset = plan["assets"][0]
        self.assertEqual(asset["raw_file"], "manual\\nota.txt" if "\\" in asset["raw_file"] else "manual/nota.txt")
        self.assertEqual(asset["sha256"], hashlib.sha256("Nota con provenance".encode("utf-8")).hexdigest())
        self.assertEqual(asset["review_status"], "unreviewed")

    def test_plan_records_inventory_read_errors_in_report(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            sidecar_path = root_dir / "broken" / "document.yaml"
            sidecar_path.parent.mkdir(parents=True)
            sidecar_path.write_text("title: [non chiuso\n", encoding="utf-8")
            output_json = tmp_dir / "input_processing_plan.json"
            output_md = tmp_dir / "input_processing_plan.md"

            plan = build_input_processing_plan(root_dir=root_dir, output_json=output_json, output_md=output_md)
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(plan["asset_count"], 0)
        self.assertEqual(plan["error_count"], 1)
        self.assertEqual(persisted["errors"][0]["kind"], "sidecar_read_error")
        self.assertIn("Errori lettura", markdown)

    def test_markdown_renderer_lists_action_counts(self) -> None:
        markdown = render_input_processing_plan_markdown(
            {
                "root_dir": "data/raw",
                "asset_count": 1,
                "error_count": 0,
                "errors": [],
                "review_status": "unreviewed",
                "action_counts": {"image_ocr_required": 1},
                "assets": [
                    {
                        "title": "Foto",
                        "recommended_action": "image_ocr_required",
                        "media_type": "image/jpeg",
                        "document_class_guess": "image_scan",
                        "raw_file": "foto.jpg",
                        "review_status": "unreviewed",
                        "reasons": ["image_media_type"],
                        "suggested_next_actions": ["manual_ocr_or_explicit_ocr_batch"],
                    }
                ],
            }
        )

        self.assertIn("# Input processing plan", markdown)
        self.assertIn("image_ocr_required", markdown)
        self.assertIn("manual_ocr_or_explicit_ocr_batch", markdown)


if __name__ == "__main__":
    unittest.main()
