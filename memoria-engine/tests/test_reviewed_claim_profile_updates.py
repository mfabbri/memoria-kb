from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import unittest
import uuid
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.candidate_profile_updates import build_reviewed_claim_profile_updates_preview  # noqa: E402
from caduti_fonti_report.document_analysis.candidate_evidence_claim_review import (  # noqa: E402
    build_candidate_evidence_claim_review,
    run_candidate_evidence_claim_review_wizard,
)


@contextmanager
def workspace_temp_dir():
    base = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base.mkdir(exist_ok=True)
    root = base / f"reviewed-updates-{uuid.uuid4().hex}"
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def create_catalog(root):
    path = root / "catalog.sqlite"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO source_documents VALUES ('document:synthetic')")
        connection.commit()
    return path


def fixture(root, choices=("a", "r", "e")):
    claims = []
    for index, (field, value) in enumerate((("birth.date", "30 novembre 1909"), ("death.date", "12 ottobre 1944"), ("occupation", "Docente"))):
        claims.append({"@type": "CandidateEvidenceClaim", "@id": f"claim:synthetic:{index}",
                       "profile_id": "person:synthetic", "source_id": "source:synthetic", "source_document_id": "document:synthetic",
                       "field": field, "value": value, "confidence": 0.8, "extraction_method": "synthetic_fixture",
                       "evidence_span": "Estratto sintetico: " + value, "review_status": "unreviewed",
                       "provenance": {"source_url": "https://example.invalid/synthetic", "page": index}})
    source = root / "claims.json"
    source.write_text(json.dumps({"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": claims}), encoding="utf-8")
    build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=root / "review")
    manifest = root / "review" / "candidate_claim_review_manifest.json"
    answers = ["reviewer-synthetic"]
    for choice in choices:
        answers.extend([choice, "nota sintetica"])
    answers.append("s")
    responses = iter(answers)
    receipt = run_candidate_evidence_claim_review_wizard(
        manifest_json=manifest, input_fn=lambda _: next(responses), output_fn=lambda _: None,
        now_fn=lambda: datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    receipt_path = root / "receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    profile = root / "profile.jsonld"
    profile.write_text(json.dumps({"@type": "PersonResearchProfile", "@id": "person:synthetic",
                                   "identity": {"canonical_name": "Persona Sintetica"}, "birth": {"date": "30 gennaio 1909"},
                                   "verified_facts": {}}), encoding="utf-8")
    return source, receipt_path, profile


class ReviewedClaimProfileUpdatesTests(unittest.TestCase):
    def test_only_accepted_claims_produce_pending_proposals_and_conflicts_keep_provenance(self):
        with workspace_temp_dir() as root:
            _, receipt, profile = fixture(root)
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            manifest = build_reviewed_claim_profile_updates_preview(receipt_json=receipt, profile_jsonld=profile, output_dir=root / "updates")
            payload = json.loads((root / "updates" / "candidate_profile_updates.jsonld").read_text(encoding="utf-8"))
            self.assertEqual(manifest["candidate_update_count"], 1)
            for reference in manifest["artifacts"].values():
                self.assertEqual(reference["sha256"], hashlib.sha256(Path(reference["path"]).read_bytes()).hexdigest())
            self.assertEqual(payload["excluded_decision_count"], 2)
            update = payload["candidate_updates"][0]
            self.assertEqual(update["review_status"], "pending")
            self.assertEqual(update["proposed_action"], "conflict_or_revision")
            self.assertEqual(update["review_bucket"], "da_discutere")
            self.assertEqual(update["current_values"], ["30 gennaio 1909"])
            self.assertEqual(update["source_claim_ids"], ["claim:synthetic:0"])
            self.assertEqual(update["source_document_ids"], ["document:synthetic"])
            self.assertEqual(update["source_urls"], ["https://example.invalid/synthetic"])
            self.assertEqual(update["review_provenance"][0]["reviewer"], "reviewer-synthetic")
            self.assertEqual(update["review_provenance"][0]["source_claim"]["provenance"]["page"], 0)
            for key in ("canonical_write_allowed", "profile_write_allowed", "claim_promotion_allowed"):
                self.assertIs(payload[key], False)
            self.assertNotIn("verified_facts", payload)
            self.assertIs(payload["source_document_existence_verified"], True)
            self.assertEqual(payload["source_documents_catalog"], json.loads(receipt.read_text(encoding="utf-8"))["source_documents_catalog"])
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_identical_retry_and_divergent_profile_retry(self):
        with workspace_temp_dir() as root:
            _, receipt, profile = fixture(root)
            output = root / "updates"
            first = build_reviewed_claim_profile_updates_preview(receipt_json=receipt, profile_jsonld=profile, output_dir=output)
            before = {path: path.read_bytes() for path in output.iterdir()}
            self.assertEqual(build_reviewed_claim_profile_updates_preview(receipt_json=receipt, profile_jsonld=profile, output_dir=output), first)
            profile.write_bytes(profile.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                build_reviewed_claim_profile_updates_preview(receipt_json=receipt, profile_jsonld=profile, output_dir=output)
            self.assertEqual({path: path.read_bytes() for path in output.iterdir()}, before)

    def test_rejected_and_needs_evidence_decisions_do_not_produce_updates(self):
        with workspace_temp_dir() as root:
            _, receipt, profile = fixture(root, choices=("r", "e", "r"))
            manifest = build_reviewed_claim_profile_updates_preview(receipt_json=receipt, profile_jsonld=profile, output_dir=root / "updates")
            self.assertEqual(manifest["candidate_update_count"], 0)

    def test_different_day_in_same_month_is_a_conflict(self):
        with workspace_temp_dir() as root:
            _, receipt, profile = fixture(root)
            payload = json.loads(profile.read_text(encoding="utf-8"))
            payload["birth"]["date"] = "10 novembre 1909"
            profile.write_text(json.dumps(payload), encoding="utf-8")
            build_reviewed_claim_profile_updates_preview(receipt_json=receipt, profile_jsonld=profile, output_dir=root / "updates")
            updates = json.loads((root / "updates" / "candidate_profile_updates.jsonld").read_text(encoding="utf-8"))
            self.assertEqual(updates["candidate_updates"][0]["proposed_action"], "conflict_or_revision")
            self.assertEqual(updates["candidate_updates"][0]["review_bucket"], "da_discutere")

    def test_tampered_receipt_fails_closed_before_output(self):
        for scenario in ("type", "status", "flag", "manifest", "queue", "input", "claim-id", "source-document", "value",
                         "duplicate", "missing", "digest", "pending", "reviewer", "timestamp", "catalog"):
            with self.subTest(scenario=scenario), workspace_temp_dir() as root:
                _, receipt_path, profile = fixture(root)
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if scenario in {"type", "status", "flag"}:
                    key, value = {"type": ("@type", "Other"), "status": ("review_status", "pending"), "flag": ("canonical_write_allowed", True)}[scenario]
                    receipt[key] = value
                elif scenario in {"manifest", "queue", "input"}:
                    reference = {"manifest": receipt["preview_manifest"], "queue": receipt["preview_artifacts"]["review_queue"], "input": receipt["claims_input"]}[scenario]
                    reference["sha256"] = "0" * 64
                elif scenario in {"claim-id", "source-document", "value", "pending", "reviewer", "timestamp"}:
                    key, value = {"claim-id": ("claim_id", "unknown"), "source-document": ("source_document_id", "other"),
                                  "value": ("candidate", {"field": "birth.date", "value": "other"}),
                                  "pending": ("decision", "pending"), "reviewer": ("reviewer", ""),
                                  "timestamp": ("reviewed_at", "2026-01-01T12:00:00")}[scenario]
                    receipt["decisions"][0][key] = value
                elif scenario == "duplicate":
                    receipt["decisions"].append(copy.deepcopy(receipt["decisions"][0]))
                elif scenario == "missing":
                    receipt["decisions"].pop()
                elif scenario == "catalog":
                    receipt["source_documents_catalog"]["database_sha256"] = "0" * 64
                else:
                    receipt["decisions_source"]["sha256"] = "0" * 64
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                with self.assertRaises(ValueError):
                    build_reviewed_claim_profile_updates_preview(receipt_json=receipt_path, profile_jsonld=profile, output_dir=root / "updates")
                self.assertFalse((root / "updates").exists())

    def test_profile_mismatch_and_changed_original_claims_are_rejected(self):
        for scenario in ("profile", "claims"):
            with self.subTest(scenario=scenario), workspace_temp_dir() as root:
                source, receipt, profile = fixture(root)
                if scenario == "profile":
                    payload = json.loads(profile.read_text(encoding="utf-8"))
                    payload["@id"] = "person:other"
                    profile.write_text(json.dumps(payload), encoding="utf-8")
                else:
                    source.write_bytes(source.read_bytes() + b" ")
                with self.assertRaises(ValueError):
                    build_reviewed_claim_profile_updates_preview(receipt_json=receipt, profile_jsonld=profile, output_dir=root / "updates")
                self.assertFalse((root / "updates").exists())

    def test_catalog_change_after_receipt_prevents_update_preview(self):
        with workspace_temp_dir() as root:
            _, receipt, profile = fixture(root)
            with closing(sqlite3.connect(root / "catalog.sqlite")) as connection:
                connection.execute("INSERT INTO source_documents VALUES ('document:added-after-review')")
                connection.commit()
            with self.assertRaises(ValueError):
                build_reviewed_claim_profile_updates_preview(receipt_json=receipt, profile_jsonld=profile, output_dir=root / "updates")
            self.assertFalse((root / "updates").exists())

    def test_installed_launcher_builds_preview_without_mutating_inputs_and_rejects_wrong_profile(self):
        launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
        with workspace_temp_dir() as root:
            _, receipt, profile = fixture(root)
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            command = [str(launcher), "review", "claims-updates-preview", "--receipt", str(receipt),
                       "--profile-jsonld", str(profile), "--output-dir", str(root / "updates")]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("candidate_profile_updates_manifest.json", completed.stdout)
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            payload = json.loads((root / "updates" / "candidate_profile_updates.jsonld").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["candidate_updates"]), 1)
            self.assertEqual(payload["candidate_updates"][0]["review_status"], "pending")
            profile_payload = json.loads(profile.read_text(encoding="utf-8"))
            profile_payload["@id"] = "person:other"
            profile.write_text(json.dumps(profile_payload), encoding="utf-8")
            command[-1] = str(root / "wrong-profile")
            invalid = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(invalid.returncode, 1)
            self.assertFalse((root / "wrong-profile").exists())


if __name__ == "__main__":
    unittest.main()
