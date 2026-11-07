from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.event_preview_pipeline import main, run_historical_event_preview


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "events" / "battaglia-purocielo.jsonld"


class HistoricalEventPreviewPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("event-pipeline-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.segments = self.root / "segments"
        self.event = self.root / "event.jsonld"
        self.event.write_bytes(FIXTURE.read_bytes())
        self.index = self.write(self.root / "index.json", {
            "@type": "HistoricalEventIndex", "events": [json.loads(self.event.read_text(encoding="utf-8"))],
        })
        self.claims = self.write(self.root / "claims.json", {
            "@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": [{
                "@type": "CandidateEvidenceClaim", "@id": "claim:one", "event_id": "event:battaglia-purocielo",
                "source_id": "fixture", "source_document_id": "doc:one", "field": "event.date_start",
                "value": "1944-10-10", "confidence": 0.7, "review_status": "unreviewed",
                "weak_segment_id": "segment:one", "chunk_id": "chunk:one", "evidence_span": "Battaglia di Purocielo",
            }],
        })
        self.segment = self.write(self.segments / "one.weak-segments.json", {
            "@type": "WeakDocumentSegmentDocument", "source_id": "fixture", "source_document_id": "doc:one",
            "segments": [{"segment_id": "segment:one", "chunk_id": "chunk:one",
                          "segment_type": "archival_reference_context",
                          "text": "La Battaglia di Purocielo compare nella relazione."}],
        })
        self.output = self.root / "preview"

    def write(self, path: Path, payload: object) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def run_preview(self, output: Path | None = None) -> dict:
        return run_historical_event_preview(segments_dir=self.segments, events_index_json=self.index,
            event_jsonld=self.event, candidate_claims_json=self.claims, output_dir=output or self.output)

    def test_composes_review_artifacts_and_hash_bound_manifest_without_changing_inputs(self) -> None:
        originals = {path: path.read_bytes() for path in (self.event, self.index, self.claims, self.segment, FIXTURE)}
        manifest = self.run_preview()
        self.assertEqual(manifest["counts"], {"documents": 1, "event_mentions": 1, "event_links": 1,
                                            "candidate_updates": 1, "skipped_claims": 0})
        self.assertEqual(manifest["source_document_ids"], ["doc:one"])
        self.assertEqual(manifest["source_ids"], ["fixture"])
        self.assertEqual(manifest["review_status"], "pending")
        self.assertTrue(manifest["requires_human_review"])
        for flag in ("apply_allowed", "automatic_merge_allowed", "event_write_allowed", "claim_extraction_allowed", "network_access_allowed"):
            self.assertFalse(manifest[flag])
        artifacts = manifest["artifacts"]
        for reference in [artifacts[key] for key in ("mention_summary", "event_links", "event_updates")] + artifacts["mention_documents"]:
            self.assertEqual(reference["sha256"], hashlib.sha256(Path(reference["path"]).read_bytes()).hexdigest())
        updates = json.loads(Path(artifacts["event_updates"]["path"]).read_text(encoding="utf-8"))
        update = updates["candidate_updates"][0]
        self.assertEqual(update["review_status"], "pending")
        self.assertEqual(update["candidate_document_event_links"][0]["review_status"], "unreviewed")
        self.assertEqual(update["source_claims"][0]["evidence_span"], "Battaglia di Purocielo")
        for path, original in originals.items():
            self.assertEqual(path.read_bytes(), original)

    def test_identical_retry_is_byte_identical_and_tampered_artifact_is_rejected(self) -> None:
        first = self.run_preview()
        snapshot = {path: path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        self.assertEqual(self.run_preview(), first)
        self.assertEqual({path: path.read_bytes() for path in snapshot}, snapshot)
        Path(first["artifacts"]["event_updates"]["path"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "artifact has changed"):
            self.run_preview()

    def test_overlapping_output_directories_are_rejected_before_writes(self) -> None:
        for output in (self.segments, self.segments / "generated", self.root, self.event):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, "must not overlap"):
                self.run_preview(output)
        self.assertFalse(self.output.exists())

    def test_mention_filenames_do_not_interpret_source_identifiers_as_paths(self) -> None:
        segment = json.loads(self.segment.read_text(encoding="utf-8"))
        segment["source_id"] = ".."
        self.write(self.segment, segment)
        claims = json.loads(self.claims.read_text(encoding="utf-8"))
        claims["candidate_evidence_claims"][0]["source_id"] = ".."
        self.write(self.claims, claims)
        manifest = self.run_preview()
        self.assertEqual(manifest["counts"]["candidate_updates"], 1)
        for reference in manifest["artifacts"]["mention_documents"]:
            self.assertTrue(Path(reference["path"]).resolve().is_relative_to(self.output.resolve()))

    def test_retry_rejects_a_manifest_that_enables_apply(self) -> None:
        manifest = self.run_preview()
        manifest["apply_allowed"] = True
        self.write(self.output / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "different preview"):
            self.run_preview()

    def test_invalid_mismatched_or_multi_event_index_is_rejected_before_output(self) -> None:
        entry = json.loads(self.event.read_text(encoding="utf-8"))
        for payload in ({"@type": "Other", "events": [entry]},
                        {"@type": "HistoricalEventIndex", "events": [entry, entry]},
                        {"@type": "HistoricalEventIndex", "events": [{**entry, "event_id": "event:other"}]},
                        {"@type": "HistoricalEventIndex", "events": [{**entry, "label": "Different event"}]}):
            self.write(self.index, payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.run_preview()
            self.assertFalse(self.output.exists())

    def test_changed_input_or_unowned_output_is_rejected_without_overwriting(self) -> None:
        self.run_preview()
        manifest_before = (self.output / "manifest.json").read_bytes()
        self.write(self.claims, {"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": []})
        with self.assertRaisesRegex(ValueError, "different preview"):
            self.run_preview()
        self.assertEqual((self.output / "manifest.json").read_bytes(), manifest_before)
        self.write(self.root / "unowned" / "keep.json", {"keep": True})
        with self.assertRaises(ValueError):
            self.run_preview(self.root / "unowned")
        self.assertEqual(json.loads((self.root / "unowned" / "keep.json").read_text()), {"keep": True})

    def test_cli_requires_inputs_and_writes_the_fixture_preview(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as missing:
            main([])
        self.assertEqual(missing.exception.code, 2)
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            result = main(["--segments-dir", str(self.segments), "--events-index-json", str(self.index),
                           "--event-jsonld", str(self.event), "--candidate-claims-json", str(self.claims),
                           "--output-dir", str(self.output)])
        self.assertEqual(result, 0)
        self.assertIn("event:battaglia-purocielo", stdout.getvalue())
        self.assertTrue((self.output / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
