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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.candidate_evidence_claims import (
    build_source_report_candidate_claims,  # noqa: E402
)


@contextmanager
def workspace_temp_dir():
    base = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base.mkdir(exist_ok=True)
    root = base / f"report-claims-{uuid.uuid4().hex}"
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


def report_fixture():
    document = {"document_id": "document:synthetic", "source_id": "source:synthetic", "title": "Scheda sintetica",
                "url": "https://example.invalid/detail", "access_date": "2026-01-01", "media_type": "text/html",
                "content_hash": "synthetic-content-hash", "raw_text": "Testo sintetico non usato come claim.",
                "metadata": {"profile_id": "person:synthetic", "detail_assessment": "claim_candidates_extracted"}}
    claim = {"claim_id": "claim:synthetic", "subject_id": "person:synthetic", "field": "birth.date",
             "value": "30 novembre 1909", "normalized_value": "1909-11-30", "source_document_id": document["document_id"],
             "source_url": document["url"], "quote": "Nato il 30 novembre 1909 (fixture).",
             "extraction_method": "detail_logic", "confidence": 0.8, "review_status": "unreviewed",
             "created_at": "2026-01-01T12:00:00+00:00"}
    entry = {"profile_id": "person:synthetic", "result": {"source_id": "source:synthetic", "status": "candidate_results",
                                                          "query": "query sintetica"},
             "documents": [document], "claims": [claim], "selected_attempt_ids": ["query-name", "query-year"],
             "matched_planned_attempt_id": "query-name"}
    return {"input_mode": "person_profiles_jsonld", "selected_attempt_ids": ["query-name", "query-year"],
            "source_selection": {"selected_source_ids": ["source:synthetic"]},
            "profiles": [{"profile_id": "person:synthetic", "canonical_name": "Persona Sintetica", "results": [entry]},
                         {"profile_id": "person:other", "results": []}]}


def write_report(root, payload):
    path = root / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class SourceReportCandidateClaimsTests(unittest.TestCase):
    def test_preserves_claim_document_attempt_provenance_and_hashes_without_promotion(self):
        with workspace_temp_dir() as root:
            report = report_fixture()
            path = write_report(root, report)
            before = path.read_bytes()
            manifest = build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=root / "claims")
            payload = json.loads((root / "claims" / "candidate_evidence_claims.json").read_text(encoding="utf-8"))
            item = payload["candidate_evidence_claims"][0]
            original = report["profiles"][0]["results"][0]["claims"][0]
            self.assertEqual(item["source_report_claim"], original)
            for key in ("claim_id", "subject_id", "field", "value", "normalized_value", "quote", "confidence", "extraction_method", "review_status"):
                self.assertEqual(item[key], original[key])
            self.assertEqual(item["@id"], original["claim_id"])
            self.assertEqual(item["source_id"], "source:synthetic")
            self.assertEqual(item["source_document_id"], "document:synthetic")
            self.assertEqual(item["source_url"], "https://example.invalid/detail")
            self.assertEqual(item["access_date"], "2026-01-01")
            self.assertEqual(item["selected_attempt_ids"], ["query-name", "query-year"])
            self.assertEqual(item["matched_planned_attempt_id"], "query-name")
            self.assertEqual(item["provenance"]["source_document"]["metadata"]["profile_id"], "person:synthetic")
            self.assertNotIn("raw_text", item["provenance"]["source_document"])
            self.assertEqual(manifest["source_report"]["sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(manifest["selected_source_ids"], ["source:synthetic"])
            self.assertIs(manifest["source_selection_declared"], True)
            for reference in manifest["artifacts"].values():
                self.assertEqual(reference["sha256"], hashlib.sha256(Path(reference["path"]).read_bytes()).hexdigest())
            self.assertEqual(path.read_bytes(), before)
            for key in ("source_document_existence_verified", "canonical_write_allowed", "claim_promotion_allowed", "profile_write_allowed"):
                self.assertIs(payload[key], False)
                self.assertIs(manifest[key], False)

    def test_malformed_links_duplicates_and_review_states_fail_before_output(self):
        scenarios = ("unknown-document", "other-result-document", "duplicate-document", "duplicate-claim", "duplicate-profile",
                     "missing-profile", "result-profile", "subject", "source", "document-profile", "claim-url", "reviewed",
                     "missing-claim-id", "missing-quote", "missing-method", "bad-confidence", "bad-access", "bad-attempt", "missing-profile-id",
                     "unselected-source", "missing-selection", "claim-profile", "claim-id-conflict")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), workspace_temp_dir() as root:
                report = report_fixture()
                entry = report["profiles"][0]["results"][0]
                claim, document = entry["claims"][0], entry["documents"][0]
                if scenario == "unknown-document":
                    claim["source_document_id"] = "unknown"
                elif scenario == "other-result-document":
                    extra = copy.deepcopy(entry)
                    extra["claims"] = []
                    extra["documents"][0]["document_id"] = "document:elsewhere"
                    report["profiles"][0]["results"].append(extra)
                    claim["source_document_id"] = "document:elsewhere"
                elif scenario == "duplicate-document":
                    entry["documents"].append(copy.deepcopy(document))
                elif scenario == "duplicate-claim":
                    entry["claims"].append(copy.deepcopy(claim))
                elif scenario == "duplicate-profile":
                    report["profiles"].append(copy.deepcopy(report["profiles"][0]))
                elif scenario == "missing-profile":
                    report["profiles"].pop(0)
                elif scenario == "result-profile":
                    entry["profile_id"] = "person:other"
                elif scenario == "subject":
                    claim["subject_id"] = "person:other"
                elif scenario == "source":
                    document["source_id"] = "source:other"
                elif scenario == "document-profile":
                    document["metadata"]["profile_id"] = "person:other"
                elif scenario == "claim-url":
                    claim["source_url"] = "https://example.invalid/other"
                elif scenario == "reviewed":
                    claim["review_status"] = "approved"
                elif scenario in {"missing-claim-id", "missing-quote", "missing-method"}:
                    key = {"missing-claim-id": "claim_id", "missing-quote": "quote", "missing-method": "extraction_method"}[scenario]
                    claim[key] = ""
                elif scenario == "bad-confidence":
                    claim["confidence"] = True
                elif scenario == "bad-access":
                    document["access_date"] = "yesterday"
                elif scenario == "bad-attempt":
                    entry["matched_planned_attempt_id"] = "unselected"
                elif scenario == "unselected-source":
                    report["source_selection"]["selected_source_ids"] = ["source:other"]
                elif scenario == "missing-selection":
                    del report["source_selection"]
                elif scenario == "claim-profile":
                    claim["profile_id"] = "person:other"
                elif scenario == "claim-id-conflict":
                    claim["@id"] = "claim:other"
                else:
                    del entry["profile_id"]
                path = write_report(root, report)
                with self.assertRaises(ValueError):
                    build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=root / "claims")
                self.assertFalse((root / "claims").exists())

    def test_malformed_report_shapes_are_rejected(self):
        for payload in ([], {}, {"@type": "Other", "profiles": []}, {"@type": "SourceResearchReport", "profiles": ["bad"]}):
            with self.subTest(payload=payload), workspace_temp_dir() as root:
                path = write_report(root, payload)
                with self.assertRaises(ValueError):
                    build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=root / "claims")

    def test_repeated_document_in_separate_results_keeps_each_attempt_context(self):
        with workspace_temp_dir() as root:
            report = report_fixture()
            second = copy.deepcopy(report["profiles"][0]["results"][0])
            second["claims"][0]["claim_id"] = "claim:second-attempt"
            second["matched_planned_attempt_id"] = "query-year"
            report["profiles"][0]["results"].append(second)
            path = write_report(root, report)
            build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=root / "claims")
            payload = json.loads((root / "claims" / "candidate_evidence_claims.json").read_text(encoding="utf-8"))
            self.assertEqual([item["matched_planned_attempt_id"] for item in payload["candidate_evidence_claims"]], ["query-name", "query-year"])

    def test_identical_retry_and_changed_input_refusal_preserve_existing_output(self):
        with workspace_temp_dir() as root:
            path = write_report(root, report_fixture())
            output = root / "claims"
            first = build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=output)
            before = {item: item.read_bytes() for item in output.iterdir()}
            self.assertEqual(build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=output), first)
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=output)
            self.assertEqual({item: item.read_bytes() for item in output.iterdir()}, before)

    def test_explicit_report_type_and_zero_claim_result_remain_unreviewed(self):
        with workspace_temp_dir() as root:
            report = report_fixture()
            del report["input_mode"]
            report["@type"] = "SourceResearchReport"
            del report["source_selection"]
            report["profiles"][0]["results"][0]["claims"] = []
            path = write_report(root, report)
            manifest = build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=root / "claims")
            self.assertEqual(manifest["claim_count"], 0)
            self.assertEqual(manifest["review_status"], "unreviewed")
            self.assertIs(manifest["source_selection_declared"], False)

    def test_scalar_result_status_derives_source_only_from_linked_document(self):
        for explicit_type in (False, True):
            with self.subTest(explicit_type=explicit_type), workspace_temp_dir() as root:
                report = report_fixture()
                report["profiles"][0]["results"][0]["result"] = "candidate_results"
                if explicit_type:
                    report["@type"] = "SourceResearchReport"
                    del report["input_mode"], report["source_selection"]
                path = write_report(root, report)
                manifest = build_source_report_candidate_claims(report_json=path, profile_id="person:synthetic", output_dir=root / "claims")
                payload = json.loads((root / "claims" / "candidate_evidence_claims.json").read_text(encoding="utf-8"))
                self.assertEqual(payload["candidate_evidence_claims"][0]["source_id"], "source:synthetic")
                self.assertEqual(manifest["source_selection_declared"], not explicit_type)

    def test_installed_launcher_builds_claims_then_review_preview_and_rejects_bad_linkage(self):
        launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
        with workspace_temp_dir() as root:
            report = report_fixture()
            path = write_report(root, report)
            before = path.read_bytes()
            command = [str(launcher), "review", "claims-build", "--report-json", str(path), "--profile-id", "person:synthetic", "--output-dir", str(root / "claims")]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(path.read_bytes(), before)
            candidate_path = root / "claims" / "candidate_evidence_claims.json"
            review = subprocess.run([str(launcher), "review", "claims-preview", "--claims-json", str(candidate_path),
                                     "--source-documents-db", str(create_catalog(root)), "--output-dir", str(root / "review")],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(review.returncode, 0, review.stderr)
            report["profiles"][0]["results"][0]["claims"][0]["source_document_id"] = "missing"
            write_report(root, report)
            command[-1] = str(root / "invalid")
            invalid = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(invalid.returncode, 1)
            self.assertFalse((root / "invalid").exists())


if __name__ == "__main__":
    unittest.main()
