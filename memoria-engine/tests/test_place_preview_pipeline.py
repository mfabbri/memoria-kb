from __future__ import annotations

import hashlib
import json
import sqlite3
import shutil
import sys
import unittest
import uuid
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.place_preview_pipeline import run_place_preview


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "places" / "purocielo.jsonld"


class PlacePreviewPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("place-pipeline-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.segments = self.root / "segments"
        self.segments.mkdir()
        self.segment = self.write(self.segments / "doc.weak-segments.json", {
            "@type": "WeakDocumentSegmentDocument", "source_id": "fixture", "source_document_id": "doc:one",
            "segments": [{"segment_id": "segment:one", "chunk_id": "chunk:one",
                "segment_type": "archival_reference_context", "text": "La località Purocielo compare nella relazione."}],
        })
        self.place = self.root / "purocielo.jsonld"
        self.place.write_bytes(FIXTURE.read_bytes())
        self.index = self.write(self.root / "places.index.json", {"places": [{"place_id": "place:purocielo",
            "preferred_label": "Purocielo", "file": self.place.name}]})
        self.claims = self.write(self.root / "claims.json", {"@type": "CandidateEvidenceClaimSet",
            "candidate_evidence_claims": [{"@type": "CandidateEvidenceClaim", "@id": "claim:one",
                "place_id": "place:purocielo", "field": "place.alternate_label", "value": "Puro Cielo",
                "source_id": "fixture", "source_document_id": "doc:one", "confidence": 0.7,
                "review_status": "unreviewed", "evidence_span": "Purocielo"}]})
        self.output = self.root / "preview"
        self.catalog = self.root / "evidence.sqlite"
        with closing(sqlite3.connect(self.catalog)) as connection:
            connection.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO source_documents VALUES ('doc:one')")
            connection.commit()

    def write(self, path: Path, value: object) -> Path:
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def run_preview(self, output: Path | None = None) -> dict:
        return run_place_preview(segments_dir=self.segments, places_index_json=self.index,
            place_jsonld=self.place, candidate_claims_json=self.claims,
            source_documents_db=self.catalog, output_dir=output or self.output)

    def test_composes_hash_bound_review_artifacts_without_changing_inputs(self) -> None:
        original = {p: p.read_bytes() for p in (self.segment, self.place, self.index, self.claims, self.catalog, FIXTURE)}
        manifest = self.run_preview()
        self.assertEqual(manifest["counts"]["place_links"], 1)
        self.assertEqual(manifest["counts"]["candidate_updates"], 1)
        self.assertEqual(manifest["catalog_resolved_source_document_ids"], ["doc:one"])
        self.assertEqual(manifest["review_status"], "pending")
        for flag in ("apply_allowed", "automatic_merge_allowed", "place_write_allowed", "claim_extraction_allowed", "network_access_allowed"):
            self.assertFalse(manifest[flag])
        artifacts = manifest["artifacts"]
        refs = [artifacts[k] for k in ("mention_summary", "place_links", "place_updates")] + artifacts["mention_documents"]
        for ref in refs:
            self.assertEqual(ref["sha256"], hashlib.sha256(Path(ref["path"]).read_bytes()).hexdigest())
        for path, data in original.items():
            self.assertEqual(path.read_bytes(), data)

    def test_identical_retry_and_tamper_rejection(self) -> None:
        first = self.run_preview()
        snapshot = {p: p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(self.run_preview(), first)
        self.assertEqual({p: p.read_bytes() for p in snapshot}, snapshot)
        Path(first["artifacts"]["place_updates"]["path"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "intact identical preview"):
            self.run_preview()

    def test_output_overlap_and_index_mismatch_fail_before_writes(self) -> None:
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.run_preview(self.segments)
        self.write(self.index, {"places": [{"place_id": "place:other", "file": self.place.name}]})
        with self.assertRaisesRegex(ValueError, "selected Place"):
            self.run_preview()
        self.assertFalse(self.output.exists())

    def test_missing_source_document_fails_closed(self) -> None:
        with closing(sqlite3.connect(self.catalog)) as connection:
            connection.execute("DELETE FROM source_documents")
            connection.commit()
        with self.assertRaisesRegex(ValueError, "absent from catalog"):
            self.run_preview()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
