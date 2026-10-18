from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from caduti_fonti_report.document_analysis.ocr_alert_dispositions import audit_ocr_alert_dispositions
from caduti_fonti_report.memoria_cli import main


class OcrAlertDispositionsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.structure = {"@type": "DocumentStructure", "schema_version": "1.0", "page_id": "p1",
            "blocks": [
                {"block_id": "b1", "text": "Xyz aa Xyz", "source_region_ids": ["r1"]},
                {"block_id": "b2", "text": "Zqx", "source_region_ids": ["r2"]},
            ]}
        self.write("structure.json", self.structure)
        self.review = {"@type": "OcrDocumentLexiconReview", "schema_version": "1.0",
            "blocks": [
                {"page_id": "p1", "block_id": "b1", "text": "Xyz aa Xyz", "source_region_ids": ["r1"],
                 "tokens": [self.token("Xyz", 0, 3), self.token("Xyz", 7, 10)]},
                {"page_id": "p1", "block_id": "b2", "text": "Zqx", "source_region_ids": ["r2"],
                 "tokens": [self.token("Zqx", 0, 3)]},
            ]}
        self.review["source_structure_digest"] = self.digest("structure.json")
        self.write("review.json", self.review)
        self.ledger = {"@type": "OcrVisualReviewLedger", "schema_version": "1.0",
            "source_structure_digest": self.digest("structure.json"),
            "observations": [
                self.observation("obs-b1", "b1", "Xyz aa Abc"),
                self.observation("obs-b2", "b2", "Zqx"),
            ]}
        self.write("ledger.json", self.ledger)
        self.visual = {"@type": "OcrVisualReviewLedgerAudit", "schema_version": "1.0",
            "inputs": {"structure": {"digest": self.digest("structure.json")},
                       "ledger": {"digest": self.digest("ledger.json")}},
            "checks": {"issues": [], "issue_count": 0}, "processability_status": "diagnostic_only",
            "visual_coverage_status": "complete_for_declared_units", "semantic_accuracy_status": "not_attested",
            "human_review_request_allowed": False, "machine_pass": False, "human_verified": False,
            "gold_promotion_allowed": False}
        self.write("visual.json", self.visual)
        self.dispositions = {"@type": "OcrLexicalDispositionLedger", "schema_version": "1.0",
            "source_structure_digest": self.digest("structure.json"),
            "source_lexicon_review_digest": self.digest("review.json"),
            "source_visual_audit_digest": self.digest("visual.json"),
            "dispositions": [
                self.disposition("b1", 0, 3, "Xyz", "visually_confirmed_candidate", "obs-b1", "lettere coerenti"),
                self.disposition("b1", 7, 10, "Xyz", "visual_correction_proposed", "obs-b1", "lettura visiva diversa", "Abc"),
                self.disposition("b2", 0, 3, "Zqx", "unresolved", "obs-b2", "grafia ancora incerta"),
            ]}
        self.write("dispositions.json", self.dispositions)

    @staticmethod
    def token(raw, start, end):
        return {"raw_token": raw, "start": start, "end": end, "status": "not_found"}

    @staticmethod
    def observation(observation_id, block_id, text):
        return {"observation_id": observation_id, "unit_type": "block", "unit_id": block_id,
                "outcome": "readable", "text": text}

    @staticmethod
    def disposition(block_id, start, end, raw, status, observation_id, reason, replacement=None):
        result = {"page_id": "p1", "block_id": block_id, "start": start, "end": end, "raw_token": raw,
                  "disposition": status, "visual_observation_id": observation_id, "reason": reason}
        if replacement is not None:
            result["replacement_text"] = replacement
        return result

    def write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def digest(self, name):
        return "sha256:" + hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def audit(self):
        return audit_ocr_alert_dispositions(structure_path=self.root / "structure.json",
            lexicon_review_path=self.root / "review.json", visual_audit_path=self.root / "visual.json",
            ledger_path=self.root / "ledger.json", dispositions_path=self.root / "dispositions.json")

    def test_all_alert_occurrences_get_distinct_dispositions_and_residual_group(self):
        report = self.audit()
        self.assertEqual(report["checks"]["issues"], [])
        self.assertEqual(report["counts"], {"candidate_blocks": 2, "lexical_alerts": 3, "dispositions": 3,
            "visually_confirmed": 1, "correction_proposals": 1, "unresolved": 1, "manual_action_groups": 1})
        self.assertEqual(report["residual_groups"][0]["block_id"], "b2")
        self.assertEqual(report["manual_action_count"], 1)
        self.assertFalse(report["human_review_request_allowed"])
        self.assertFalse(report["machine_pass"])
        self.assertEqual(report["semantic_accuracy_status"], "not_attested")

    def test_missing_duplicate_and_forged_span_dispositions_block(self):
        self.dispositions["dispositions"].pop()
        self.write("dispositions.json", self.dispositions)
        self.assertIn("disposition_coverage_mismatch", {i["code"] for i in self.audit()["checks"]["issues"]})
        self.dispositions["dispositions"].append(dict(self.dispositions["dispositions"][0]))
        self.write("dispositions.json", self.dispositions)
        self.assertIn("invalid_or_duplicate_disposition", {i["code"] for i in self.audit()["checks"]["issues"]})
        self.dispositions["dispositions"][0]["start"] = 1
        self.write("dispositions.json", self.dispositions)
        self.assertIn("disposition_coverage_mismatch", {i["code"] for i in self.audit()["checks"]["issues"]})

    def test_visual_observation_must_support_disposition_and_correction(self):
        self.dispositions["dispositions"][1]["replacement_text"] = "Wrong"
        self.write("dispositions.json", self.dispositions)
        self.assertIn("invalid_visual_correction_proposal", {i["code"] for i in self.audit()["checks"]["issues"]})
        self.dispositions["dispositions"][1]["replacement_text"] = "Abc"
        self.dispositions["dispositions"][0]["visual_observation_id"] = "missing"
        self.write("dispositions.json", self.dispositions)
        self.assertIn("visual_observation_mismatch", {i["code"] for i in self.audit()["checks"]["issues"]})

    def test_stale_artifacts_or_incomplete_visual_audit_block(self):
        self.review["source_structure_digest"] = "sha256:" + "0" * 64
        self.write("review.json", self.review)
        self.assertIn("stale_candidate_artifact", {i["code"] for i in self.audit()["checks"]["issues"]})
        self.review["source_structure_digest"] = self.digest("structure.json")
        self.write("review.json", self.review)
        self.visual["human_review_request_allowed"] = True
        self.write("visual.json", self.visual)
        self.assertIn("unsuccessful_visual_audit", {i["code"] for i in self.audit()["checks"]["issues"]})

    def test_cli_preview_and_blocked_exit(self):
        args = ["documents", "ocr-alert-dispositions-audit", "--structure", str(self.root / "structure.json"),
            "--lexicon-review", str(self.root / "review.json"), "--visual-audit", str(self.root / "visual.json"),
            "--ledger", str(self.root / "ledger.json"), "--dispositions", str(self.root / "dispositions.json")]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["processability_status"], "diagnostic_only")
        self.dispositions["dispositions"] = []
        self.write("dispositions.json", self.dispositions)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 1)


if __name__ == "__main__":
    unittest.main()
