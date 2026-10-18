from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.memoria_cli import main  # noqa: E402


class OcrTransformStructureCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest_path = self.root / "pilot-manifest.json"
        self.output_dir = self.root / "structured-output"
        self.pages = [self._page("page-26", "numbered_report"), self._page("page-28", "leader_list_report")]
        self.profiles = {page["page_id"]: profile for page, profile in zip(self.pages, ("numbered_report", "leader_list_report"))}
        self._write_manifest()

    def _page(self, page_id: str, _profile: str) -> dict:
        source_path = self.root / f"{page_id}.tif"
        source_path.write_bytes(f"source:{page_id}".encode())
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        artifact_rel = f"pages/{page_id}/variants/contrast-x1.8.png"
        artifact_path = self.root / artifact_rel
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(f"variant:{page_id}".encode())
        artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        transform_id = "t36-transform-tiling-pilot-v1:contrast"
        evidence = {
            "@type": "OcrPageEvidence", "schema_version": "1.0", "page_id": page_id,
            "source_image_hash": source_hash, "transform_id": transform_id,
            "engine": "paddle-ocr-v5", "language": "deu",
            "source_page": {
                "original_page": {"page_id": page_id, "source_file": str(source_path),
                                  "source_dimensions": {"width": 100, "height": 50},
                                  "source_image_hash": source_hash},
                "variant_id": "contrast", "target": "full_page", "tile_id": None,
            },
            "model": {"ocr_version": "PP-OCRv5", "name": "latin_PP-OCRv5_mobile_rec"},
            "image_transform": {"id": transform_id, "parameters": {"operation": "contrast", "factor": 1.8}},
            "regions": [{"region_id": f"{page_id}-r1", "text": "1. Example heading",
                         "geometry": {"bbox": [5, 5, 90, 20]}, "confidence": 0.9}],
        }
        return {
            "page_id": page_id,
            "source": {"path": str(source_path), "sha256": source_hash,
                       "image_dimensions": {"width": 100, "height": 50}},
            "variants": [{
                "variant_id": "contrast", "sha256": artifact_hash, "path": artifact_rel,
                "transform": {"id": transform_id, "parameters": {"operation": "contrast", "factor": 1.8}},
                "ocr_outputs": [{"target": "full_page", "artifact": artifact_rel,
                                 "artifact_sha256": artifact_hash, "source_bbox": [0, 0, 100, 50],
                                 "structured_evidence": evidence}],
            }],
        }

    def _write_manifest(self) -> None:
        payload = {"@type": "OcrTransformPilot", "schema_version": "1.0", "review_status": "unreviewed",
                   "accuracy_claim": "none_without_human_reference", "language": "deu", "pages": self.pages}
        self.manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _args(self, *, apply: bool = False, profiles: dict[str, str] | None = None,
              output_dir: Path | None = None) -> list[str]:
        selected = profiles if profiles is not None else self.profiles
        args = ["documents", "ocr-transform-structure", "--manifest", str(self.manifest_path),
                "--variant", "contrast", "--output-dir", str(output_dir or self.output_dir)]
        for page_id, profile in selected.items():
            args.extend(["--page-profile", f"{page_id}={profile}"])
        if apply:
            args.append("--apply")
        return args

    def _run(self, args: list[str]) -> tuple[int, dict, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args)
        return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, stderr.getvalue()

    def test_preview_is_read_only_and_reports_required_pending_stages(self) -> None:
        code, report, stderr = self._run(self._args())
        self.assertEqual((code, stderr), (0, ""))
        self.assertFalse(self.output_dir.exists())
        self.assertEqual(report["operation_status"], "preview")
        self.assertEqual(report["selected_variant"], "contrast")
        self.assertEqual(len(report["pages"]), 2)
        self.assertEqual(report["pages"][0]["profile"], "numbered_report")
        self.assertIn("tesseract_comparison", report["pending_stages"])
        self.assertIn("page_level_review", report["pending_stages"])
        self.assertFalse(report["machine_pass"])
        self.assertFalse(report["auto_validation_enabled"])

    def test_apply_writes_hash_bound_evidence_structure_markdown_and_run_manifest(self) -> None:
        code, report, stderr = self._run(self._args(apply=True))
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(report["operation_status"], "written")
        run_manifest = json.loads((self.output_dir / "run-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(run_manifest["source_manifest"]["sha256"], hashlib.sha256(self.manifest_path.read_bytes()).hexdigest())
        self.assertEqual(run_manifest["status"], "structure_candidate_ready_pending_required_reviews")
        self.assertFalse(run_manifest["gold_promotion_allowed"])
        for page in report["pages"]:
            for artifact_type in ("evidence", "structure", "markdown"):
                artifact = self.output_dir / page[artifact_type]["path"]
                self.assertTrue(artifact.is_file())
                self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), page[artifact_type]["sha256"])
        self.assertIn("1. Example heading", (self.output_dir / "markdown" / "page-26.md").read_text(encoding="utf-8"))

    def test_rejects_missing_profile_and_tampered_variant_before_writing(self) -> None:
        code, _, stderr = self._run(self._args(profiles={"page-26": "numbered_report"}))
        self.assertEqual(code, 1)
        self.assertIn("esattamente ogni page_id", stderr)
        self.assertFalse(self.output_dir.exists())

        artifact = self.root / "pages" / "page-26" / "variants" / "contrast-x1.8.png"
        artifact.write_bytes(b"tampered")
        code, _, stderr = self._run(self._args(apply=True))
        self.assertEqual(code, 1)
        self.assertIn("SHA-256 immagine variante divergente", stderr)
        self.assertFalse(self.output_dir.exists())

    def test_rejects_artifact_name_collisions_and_non_finite_coordinates(self) -> None:
        colliding = self._page("page 26", "numbered_report")
        self.pages.append(colliding)
        self.profiles["page 26"] = "numbered_report"
        self._write_manifest()
        code, _, stderr = self._run(self._args())
        self.assertEqual(code, 1)
        self.assertIn("collidono dopo la normalizzazione", stderr)
        self.assertFalse(self.output_dir.exists())

        self.pages.pop()
        self.profiles.pop("page 26")
        self.pages[0]["variants"][0]["ocr_outputs"][0]["structured_evidence"]["regions"][0]["geometry"]["bbox"][0] = 1e999
        self._write_manifest()
        code, _, stderr = self._run(self._args())
        self.assertEqual(code, 1)
        self.assertIn("Costante JSON non finita non consentita", stderr)
        self.assertFalse(self.output_dir.exists())

    def test_rejects_output_inside_repository(self) -> None:
        repo_output = Path(__file__).resolve().parents[2] / ".tmp-ocr-transform-structure"
        code, _, stderr = self._run(self._args(output_dir=repo_output))
        self.assertEqual(code, 1)
        self.assertIn("esterna al repository", stderr)
        self.assertFalse(repo_output.exists())


if __name__ == "__main__":
    unittest.main()
