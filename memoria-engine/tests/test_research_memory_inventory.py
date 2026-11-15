from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.research_memory_inventory import build_research_memory_inventory


class ResearchMemoryInventoryTests(unittest.TestCase):
    def setUp(self):
        import uuid
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("memory-inventory-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write(self, path: Path, value: bytes) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        return hashlib.sha256(value).hexdigest()

    def receipt(self, label: str, *, tamper: bool = False) -> Path:
        base = self.root / label
        refs = {}
        for name in ("manifest.json", "claims.json", "queue.json", "review.md"):
            expected_raw = name.encode()
            raw = (b"tampered" if tamper and name == "claims.json" else expected_raw)
            path = base / name
            digest = hashlib.sha256(expected_raw).hexdigest()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            key = {"manifest.json": "preview_manifest", "claims.json": "claims_input"}.get(name)
            refs[key or name.replace(".json", "").replace(".md", "")] = {"path": str(path), "sha256": digest}
        decisions = [{"profile_id": "person:fixture:one", "claim_id": f"claim:{label}:1", "decision": "accept_candidate"}]
        db = base / "catalog.sqlite"
        self.write(db, b"catalog snapshot")
        return_data = {"@type": "CandidateEvidenceClaimReviewReceipt", "review_status": "complete", "review_complete": True,
            "decision_count": 1, "decision_counts": {"accept_candidate": 1}, "decisions": decisions,
            "preview_manifest": refs.pop("preview_manifest"), "claims_input": refs.pop("claims_input"),
            "preview_artifacts": refs, "source_documents_catalog": {"path": str(db), "database_sha256": "0" * 64}}
        receipt = base / "receipt.json"
        receipt.write_text(json.dumps(return_data), encoding="utf-8")
        return receipt

    def test_two_receipts_verify_artifacts_and_classify_catalog_drift(self):
        receipts = [self.receipt("session-one"), self.receipt("session-two")]
        out = self.root / "inventory"
        result = build_research_memory_inventory(receipt_paths=receipts, output_dir=out)
        self.assertEqual(result["receipt_count"], 2)
        self.assertEqual(result["decision_count"], 2)
        for session in result["sessions"]:
            self.assertTrue(all(x["status"] == "verified" for x in session["artifact_checks"]))
            self.assertEqual(session["catalog_snapshot_state"], "catalog_drift_since_review")
        self.assertFalse(result["canonical_write_allowed"])

    def test_missing_and_tampered_artifacts_are_diagnosed_without_changing_inputs(self):
        receipt = self.receipt("session", tamper=True)
        before = receipt.read_bytes()
        result = build_research_memory_inventory(receipt_paths=[receipt], output_dir=self.root / "inventory")
        statuses = {x["name"]: x["status"] for x in result["sessions"][0]["artifact_checks"]}
        self.assertEqual(statuses["claims_input"], "hash_mismatch")
        (receipt.parent / "queue.json").unlink()
        second = build_research_memory_inventory(receipt_paths=[receipt], output_dir=self.root / "inventory-two")
        second_statuses = {x["name"]: x["status"] for x in second["sessions"][0]["artifact_checks"]}
        self.assertEqual(second_statuses["queue"], "missing")
        self.assertEqual(receipt.read_bytes(), before)

    def test_relocation_manifest_resolves_moved_artifact_only_after_hash_check(self):
        root = self.root / "relocated"
        old = root / "old-session" / "claims.json"
        current = root / "persistent-session" / "claims.json"
        digest = self.write(current, b"unchanged claim artifact")
        manifest = {"schema": "memoria.artifact-relocation.v1", "original_directory": str(old.parent),
            "persistent_directory": str(current.parent), "files": [{"path": "claims.json", "sha256": digest}]}
        (current.parent / "artifact-relocation-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        receipt = self.receipt("relocation-session")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["claims_input"] = {"path": str(old), "sha256": digest}
        receipt = current.parent / "review-selected" / "receipt.json"
        receipt.parent.mkdir()
        receipt.write_text(json.dumps(data), encoding="utf-8")
        result = build_research_memory_inventory(receipt_paths=[receipt], output_dir=self.root / "relocation-inventory")
        checked = next(x for x in result["sessions"][0]["artifact_checks"] if x["name"] == "claims_input")
        self.assertEqual(checked["status"], "verified")
        self.assertEqual(checked["resolved_from"], "artifact-relocation-manifest")


if __name__ == "__main__":
    unittest.main()
