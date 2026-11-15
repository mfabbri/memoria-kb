from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.claim_evidence_quote_verification import verify_claim_evidence_quotes


class ClaimEvidenceQuoteVerificationTests(unittest.TestCase):
    def setUp(self):
        import uuid
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("quote-verify-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_exact_mismatch_missing_and_source_mismatch_without_input_writes(self):
        text = "Birth: 30 gennaio 1909 (oppure 30 novembre 1909)."
        doc = {"@type": "ProcessedDocumentText", "source_document_id": "doc:one", "source_id": "source:one",
            "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
        doc_path = self.root / "doc.json"
        doc_path.write_text(json.dumps(doc), encoding="utf-8")
        claims = {"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": [
            {"@type": "CandidateEvidenceClaim", "@id": "claim:exact", "source_document_id": "doc:one", "source_id": "source:one", "field": "birth.date", "value": "date", "evidence_span": "30 gennaio 1909 (oppure 30 novembre 1909)"},
            {"@type": "CandidateEvidenceClaim", "@id": "claim:normalized", "source_document_id": "doc:one", "source_id": "source:one", "field": "birth.date", "value": "date", "evidence_span": "30 gennaio 1909 oppure 30 novembre 1909"},
            {"@type": "CandidateEvidenceClaim", "@id": "claim:missing", "source_document_id": "doc:missing", "source_id": "source:one", "field": "death.date", "value": "date", "evidence_span": "1944"},
            {"@type": "CandidateEvidenceClaim", "@id": "claim:wrong-source", "source_document_id": "doc:one", "source_id": "source:two", "field": "death.date", "value": "date", "evidence_span": "1944"},
        ]}
        claim_path = self.root / "claims.json"
        claim_path.write_text(json.dumps(claims), encoding="utf-8")
        before_claims, before_doc = claim_path.read_bytes(), doc_path.read_bytes()
        result = verify_claim_evidence_quotes(claims_json=claim_path, processed_text_paths=[doc_path], output_dir=self.root / "output")
        self.assertEqual(result["status_counts"], {"exact_match": 1, "not_exact": 1, "missing_document_text": 1, "source_id_mismatch": 1})
        self.assertEqual(claim_path.read_bytes(), before_claims)
        self.assertEqual(doc_path.read_bytes(), before_doc)
        self.assertFalse(result["claims_modified"])

    def test_processed_text_hash_mismatch_fails_closed(self):
        path = self.root / "doc.json"
        path.write_text(json.dumps({"@type": "ProcessedDocumentText", "source_document_id": "doc:one",
            "source_id": "source:one", "text": "changed", "text_sha256": "0" * 64}), encoding="utf-8")
        claims = self.root / "claims.json"
        claims.write_text(json.dumps({"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": []}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "text_sha256 mismatch"):
            verify_claim_evidence_quotes(claims_json=claims, processed_text_paths=[path], output_dir=self.root / "output")


if __name__ == "__main__":
    unittest.main()
