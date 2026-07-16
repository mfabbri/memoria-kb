from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.image_preprocessing_plan import (  # noqa: E402
    build_image_preprocessing_plan,
    render_image_preprocessing_plan_markdown,
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


def write_input_plan(path: Path, assets: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "@type": "InputProcessingPlan",
                "root_dir": "data/raw",
                "asset_count": len(assets),
                "assets": assets,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class ImagePreprocessingPlanTests(unittest.TestCase):
    def test_builds_conservative_plan_from_input_processing_plan(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            input_json = tmp_dir / "input_processing_plan.json"
            output_json = tmp_dir / "image_preprocessing_plan.json"
            output_md = tmp_dir / "image_preprocessing_plan.md"
            write_input_plan(
                input_json,
                [
                    {
                        "source_document_id": "scan-1",
                        "title": "Pagina scansione",
                        "raw_file": "scan/pagina_001.jpg",
                        "sidecar_file": "scan/pagina_001.jpg.document.yaml",
                        "media_type": "image/jpeg",
                        "document_class_guess": "image_scan",
                        "recommended_action": "image_ocr_required",
                        "review_status": "unreviewed",
                    },
                    {
                        "source_document_id": "map-1",
                        "title": "Carta operativa",
                        "raw_file": "mappe/carta-operativa-1944.jpg",
                        "media_type": "image/jpeg",
                        "document_class_guess": "historical_map",
                        "recommended_action": "historical_map_georeferencing_required",
                    },
                    {
                        "source_document_id": "photo-1",
                        "title": "Ritratto partigiano",
                        "raw_file": "foto/ritratto.jpg",
                        "media_type": "image/jpeg",
                        "document_class_guess": "photograph",
                        "recommended_action": "manual_review_required",
                    },
                    {
                        "source_document_id": "text-1",
                        "title": "Nota",
                        "raw_file": "docs/nota.txt",
                        "media_type": "text/plain",
                        "document_class_guess": "text_document",
                        "recommended_action": "text_document_ready",
                    },
                ],
            )

            plan = build_image_preprocessing_plan(
                input_plan_json=input_json,
                output_json=output_json,
                output_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(plan["@type"], "ImagePreprocessingPlan")
        self.assertEqual(plan["image_count"], 3)
        self.assertEqual(persisted["image_class_counts"]["document_scan_dark_text"], 1)
        self.assertEqual(persisted["image_class_counts"]["historical_map"], 1)
        self.assertEqual(persisted["image_class_counts"]["photograph_non_text"], 1)
        by_id = {item["image_id"]: item for item in persisted["items"]}
        self.assertEqual(by_id["scan-1"]["recommended_preprocessing"], "dark_foreground_binary")
        self.assertEqual(by_id["scan-1"]["recommended_ocr_strategy"], "raw_ocr_first")
        self.assertEqual(by_id["map-1"]["recommended_preprocessing"], "manual_review_required")
        self.assertEqual(by_id["map-1"]["recommended_ocr_strategy"], "region_ocr_only")
        self.assertEqual(by_id["photo-1"]["recommended_preprocessing"], "none")
        self.assertEqual(by_id["photo-1"]["recommended_ocr_strategy"], "skip_ocr")
        self.assertIn("# Image preprocessing plan", markdown)
        self.assertIn("Carta operativa", markdown)

    def test_ambiguous_image_falls_back_to_manual_review(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            input_json = tmp_dir / "input_processing_plan.json"
            write_input_plan(
                input_json,
                [
                    {
                        "source_document_id": "unknown-1",
                        "raw_file": "asset/immagine.webp",
                        "media_type": "image/webp",
                        "document_class_guess": "generic_document",
                        "recommended_action": "manual_review_required",
                    }
                ],
            )

            plan = build_image_preprocessing_plan(input_plan_json=input_json)

        item = plan["items"][0]
        self.assertEqual(item["image_class_candidate"], "unknown")
        self.assertEqual(item["recommended_preprocessing"], "manual_review_required")
        self.assertEqual(item["recommended_ocr_strategy"], "manual_review_required")

    def test_markdown_renderer_handles_empty_plan(self) -> None:
        markdown = render_image_preprocessing_plan_markdown(
            {
                "input_processing_plan": "input.json",
                "root_dir": "data/raw",
                "image_count": 0,
                "review_status": "unreviewed",
                "items": [],
            }
        )

        self.assertIn("_Nessuna immagine candidata._", markdown)


if __name__ == "__main__":
    unittest.main()
