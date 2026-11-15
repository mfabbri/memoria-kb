from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.research_memory_view import build_research_memory_view


class ResearchMemoryViewTests(unittest.TestCase):
    def setUp(self):
        import uuid
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("memory-view-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def receipt(self, name: str, decision: str, value: str, source: str) -> tuple[Path, str]:
        path = self.root / name / "receipt.json"
        path.parent.mkdir(parents=True)
        item = {"profile_id": "person:fixture:one", "claim_id": "claim:birth:1", "decision": decision,
            "reviewer": "Reviewer", "reviewed_at": "2026-11-15T10:00:00Z", "source_id": source,
            "source_document_id": "doc:" + source, "source_document_title": source,
            "evidence_span": "Born on " + value, "source_claim": {"field": "birth.date", "value": value, "normalized_value": value}}
        payload = {"@type": "CandidateEvidenceClaimReviewReceipt", "review_complete": True,
            "decisions": [item]}
        raw = json.dumps(payload).encode()
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def inventory(self) -> Path:
        one, h1 = self.receipt("session-one", "accept_candidate", "1909-01-30", "source-one")
        two, h2 = self.receipt("session-two", "needs_more_evidence", "1909-11-30", "source-two")
        path = self.root / "inventory.json"
        path.write_text(json.dumps({"@type": "ResearchMemorySessionInventory", "preview_only": True,
            "profile_ids": ["person:fixture:one"], "sessions": [
                {"receipt_path": str(one), "receipt_sha256": h1}, {"receipt_path": str(two), "receipt_sha256": h2}]}), encoding="utf-8")
        return path

    def test_deterministic_view_preserves_conflicting_decisions_and_absent_feedback(self):
        inventory = self.inventory()
        first = build_research_memory_view(inventory_path=inventory, output_dir=self.root / "view-one")
        second = build_research_memory_view(inventory_path=inventory, output_dir=self.root / "view-two")
        self.assertEqual(first, second)
        self.assertEqual(len(first["claim_decisions"]), 2)
        self.assertEqual(len(first["conflicts"]), 1)
        self.assertEqual(first["feedback_state"], "not_provided")
        self.assertFalse(first["canonical_write_allowed"])

    def test_changed_receipt_after_inventory_is_rejected(self):
        inventory = self.inventory()
        receipt = Path(json.loads(inventory.read_text())["sessions"][0]["receipt_path"])
        receipt.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed since inventory"):
            build_research_memory_view(inventory_path=inventory, output_dir=self.root / "view")

    def test_view_includes_unreviewed_lineage_and_quote_status_as_diagnostics(self):
        inventory = self.inventory()
        lineage = self.root / "lineage.json"
        lineage.write_text(json.dumps({"@type": "CandidateSourceDocumentLineageSet", "preview_only": True,
            "links": [{"source_document_id": "local:1", "related_source_document_id": "online:1",
                "relation_type": "local_capture_of", "review_status": "unreviewed"}]}), encoding="utf-8")
        quotes = self.root / "quotes.json"
        quotes.write_text(json.dumps({"@type": "CandidateEvidenceQuoteVerification", "preview_only": True,
            "claims": [{"claim_id": "claim:1", "status": "not_exact"}]}), encoding="utf-8")
        view = build_research_memory_view(inventory_path=inventory, output_dir=self.root / "view",
            lineage_paths=[lineage], quote_verification_paths=[quotes])
        self.assertEqual(view["source_document_lineage"][0]["review_status"], "unreviewed")
        self.assertEqual(view["evidence_quote_checks"][0]["status"], "not_exact")
        self.assertFalse(view["claim_promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
