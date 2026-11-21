from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from caduti_fonti_report.document_analysis.research_memory_view import build_research_memory_view


class ResearchMemoryViewTests(unittest.TestCase):
    def setUp(self):
        import uuid
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("memory-view-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def receipt(self, name: str, decision: str, value: str, source: str, note: str = "") -> tuple[Path, str]:
        path = self.root / name / "receipt.json"
        path.parent.mkdir(parents=True)
        item = {"profile_id": "person:fixture:one", "claim_id": "claim:birth:1", "decision": decision,
            "reviewer": "Reviewer", "reviewed_at": "2026-11-15T10:00:00Z", "source_id": source,
            "source_document_id": "doc:" + source, "source_document_title": source,
            "evidence_span": "Born on " + value, "note": note,
            "source_claim": {"field": "birth.date", "value": value, "normalized_value": value}}
        payload = {"@type": "CandidateEvidenceClaimReviewReceipt", "review_complete": True,
            "decisions": [item]}
        raw = json.dumps(payload).encode()
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def inventory(self) -> Path:
        one, h1 = self.receipt("session-one", "accept_candidate", "1909-01-30", "source-one")
        two, h2 = self.receipt("session-two", "needs_more_evidence", "1909-11-30", "source-two",
                               "Serve una fonte indipendente.")
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
        rationale = next(row["note"] for row in first["claim_decisions"] if row["decision"] == "needs_more_evidence")
        self.assertEqual(rationale, "Serve una fonte indipendente.")
        markdown = (self.root / "view-one" / "research-memory-view.md").read_text(encoding="utf-8")
        self.assertIn("Reviewer note: `Serve una fonte indipendente.`", markdown)
        self.assertFalse(first["canonical_write_allowed"])

    def test_changed_receipt_after_inventory_is_rejected(self):
        inventory = self.inventory()
        receipt = Path(json.loads(inventory.read_text())["sessions"][0]["receipt_path"])
        receipt.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed since inventory"):
            build_research_memory_view(inventory_path=inventory, output_dir=self.root / "view")

    def test_no_results_feedback_warning_and_artifact_provenance_are_visible(self):
        inventory = self.inventory()
        outcome = self.root / "feedback-outcome.json"
        outcome.write_text(json.dumps({"@type": "FeedbackLoopOutcome",
            "feedback_loop_outcome_id": "feedback-loop-outcome:fixture",
            "profile_id": "person:fixture:one", "outcome_status": "no_results",
            "warnings": ["no_results_is_search_memory_not_historical_absence_proof"]}), encoding="utf-8")
        output_dir = self.root / "view-with-feedback"
        view = build_research_memory_view(inventory_path=inventory, output_dir=output_dir,
            feedback_outcome_paths=[outcome])
        feedback = view["feedback_outcomes"][0]
        digest = hashlib.sha256(outcome.read_bytes()).hexdigest()
        self.assertEqual(view["feedback_state"], "present")
        self.assertEqual(feedback["outcome_id"], "feedback-loop-outcome:fixture")
        self.assertEqual(feedback["outcome_status"], "no_results")
        self.assertEqual(feedback["warnings"], ["no_results_is_search_memory_not_historical_absence_proof"])
        self.assertEqual(feedback["path"], str(outcome.resolve()))
        self.assertEqual(feedback["sha256"], digest)
        markdown = (output_dir / "research-memory-view.md").read_text(encoding="utf-8")
        self.assertIn("feedback-loop-outcome:fixture", markdown)
        self.assertIn("no_results", markdown)
        self.assertIn("no_results_is_search_memory_not_historical_absence_proof", markdown)
        self.assertIn(str(outcome.resolve()), markdown)
        self.assertIn(digest, markdown)
        self.assertFalse(view["canonical_write_allowed"])

    def test_invalid_feedback_warning_shape_fails_before_output(self):
        inventory = self.inventory()
        for index, warnings in enumerate(("unexpected scalar", [""], [42])):
            with self.subTest(warnings=warnings):
                outcome = self.root / "invalid-feedback-outcome.json"
                outcome.write_text(json.dumps({"@type": "FeedbackLoopOutcome",
                    "profile_id": "person:fixture:one", "outcome_status": "no_results",
                    "warnings": warnings}), encoding="utf-8")
                output_dir = self.root / f"invalid-view-{index}"
                with self.assertRaisesRegex(ValueError, "Invalid FeedbackLoopOutcome warnings"):
                    build_research_memory_view(inventory_path=inventory, output_dir=output_dir,
                        feedback_outcome_paths=[outcome])
                self.assertFalse(output_dir.exists())

    def test_feedback_outcome_profile_must_bind_to_inventory(self):
        inventory = self.inventory()
        outcome = self.root / "profile-bound-feedback.json"
        outcome.write_text(json.dumps({"@type": "FeedbackLoopOutcome",
            "feedback_loop_outcome_id": "feedback:profile-bound", "outcome_status": "no_results",
            "search_memory_update_preview": {"profile_id": "person:fixture:one"}, "warnings": []}),
            encoding="utf-8")
        view = build_research_memory_view(inventory_path=inventory,
            output_dir=self.root / "nested-profile-view", feedback_outcome_paths=[outcome])
        self.assertEqual(view["feedback_outcomes"][0]["profile_id"], "person:fixture:one")

        invalid_payloads = [
            ({"profile_id": "person:outside-inventory"}, "not present in inventory"),
            ({"profile_id": "person:fixture:one",
              "search_memory_update_preview": {"profile_id": "person:other"}}, "Conflicting FeedbackLoopOutcome profile IDs"),
            ({}, "not present in inventory"),
            ({"search_memory_update_preview": "invalid"}, "Invalid FeedbackLoopOutcome search_memory_update_preview"),
        ]
        for index, (identity, message) in enumerate(invalid_payloads):
            with self.subTest(identity=identity):
                outcome.write_text(json.dumps({"@type": "FeedbackLoopOutcome", **identity}), encoding="utf-8")
                output_dir = self.root / f"invalid-profile-view-{index}"
                with self.assertRaisesRegex(ValueError, message):
                    build_research_memory_view(inventory_path=inventory, output_dir=output_dir,
                        feedback_outcome_paths=[outcome])
                self.assertFalse(output_dir.exists())

    def test_multiple_feedback_outcomes_keep_distinct_provenance_in_input_order(self):
        inventory = self.inventory()
        catalog_path = self.root / "source-documents.sqlite"
        catalog_bytes = b"synthetic source document catalog"
        catalog_path.write_bytes(catalog_bytes)
        catalog_digest = hashlib.sha256(catalog_bytes).hexdigest()
        catalog_verification = {"path": str(catalog_path.resolve()), "sha256": catalog_digest,
            "resolved_document_ids": ["doc:result"],
            "documents": [{"document_id": "doc:result", "title": "Synthetic result", "url": "https://example.invalid/result"}]}
        outcomes = [
            self.root / "feedback-candidate-results.json",
            self.root / "feedback-no-results.json",
        ]
        payloads = [
            {"@type": "FeedbackLoopOutcome", "feedback_loop_outcome_id": "feedback:candidates",
             "profile_id": "person:fixture:one", "outcome_status": "candidate_results", "warnings": [],
             "result_source_document_ids": ["doc:result"],
             "result_source_documents_catalog": catalog_verification},
            {"@type": "FeedbackLoopOutcome", "feedback_loop_outcome_id": "feedback:no-results",
             "profile_id": "person:fixture:one", "outcome_status": "no_results",
             "warnings": ["no_results_is_search_memory_not_historical_absence_proof"]},
        ]
        for path, payload in zip(outcomes, payloads, strict=True):
            path.write_text(json.dumps(payload), encoding="utf-8")

        output_dir = self.root / "view-with-multiple-feedback"
        view = build_research_memory_view(inventory_path=inventory, output_dir=output_dir,
            feedback_outcome_paths=outcomes)
        feedback = view["feedback_outcomes"]
        self.assertEqual([item["outcome_id"] for item in feedback],
            ["feedback:candidates", "feedback:no-results"])
        self.assertEqual([item["outcome_status"] for item in feedback],
            ["candidate_results", "no_results"])
        self.assertEqual([item["warnings"] for item in feedback], [[],
            ["no_results_is_search_memory_not_historical_absence_proof"]])
        self.assertEqual(feedback[0]["result_source_document_ids"], ["doc:result"])
        self.assertEqual(feedback[0]["result_source_documents_catalog"], catalog_verification)
        self.assertEqual(feedback[0]["result_source_attribution_status"], "unavailable")
        self.assertEqual(feedback[1]["result_source_document_ids"], [])
        self.assertIsNone(feedback[1]["result_source_documents_catalog"])
        self.assertEqual(feedback[1]["result_source_attribution_status"], "not_applicable")
        self.assertEqual([item["path"] for item in feedback], [str(path.resolve()) for path in outcomes])
        self.assertEqual([item["sha256"] for item, path in zip(feedback, outcomes, strict=True)],
            [hashlib.sha256(path.read_bytes()).hexdigest() for path in outcomes])
        persisted = json.loads((output_dir / "research-memory-view.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["feedback_outcomes"], feedback)
        markdown = (output_dir / "research-memory-view.md").read_text(encoding="utf-8")
        self.assertIn("feedback:candidates", markdown)
        self.assertIn("feedback:no-results", markdown)
        self.assertIn("no_results_is_search_memory_not_historical_absence_proof", markdown)
        self.assertIn("Result SourceDocument: `doc:result`", markdown)
        self.assertIn("Result source attribution: `unavailable`", markdown)
        self.assertIn(str(catalog_path.resolve()), markdown)
        self.assertIn(catalog_digest, markdown)

    def test_legacy_result_ids_without_catalog_snapshot_remain_unverified(self):
        inventory = self.inventory()
        outcome = self.root / "legacy-candidate-outcome.json"
        outcome.write_text(json.dumps({"@type": "FeedbackLoopOutcome",
            "feedback_loop_outcome_id": "feedback:legacy-candidate",
            "profile_id": "person:fixture:one", "outcome_status": "candidate_results",
            "result_source_document_ids": ["doc:legacy"]}), encoding="utf-8")
        view = build_research_memory_view(inventory_path=inventory,
            output_dir=self.root / "view-legacy-candidate", feedback_outcome_paths=[outcome])
        self.assertEqual(view["feedback_outcomes"][0]["result_source_document_ids"], ["doc:legacy"])
        self.assertIsNone(view["feedback_outcomes"][0]["result_source_documents_catalog"])
        self.assertEqual(view["feedback_outcomes"][0]["result_source_attribution_status"], "unavailable")

    def test_inconsistent_result_catalog_binding_fails_before_output(self):
        inventory = self.inventory()
        catalog = {"path": str((self.root / "catalog.sqlite").resolve()), "sha256": "a" * 64,
            "resolved_document_ids": ["doc:result"],
            "documents": [{"document_id": "doc:result", "title": "Synthetic result", "url": "",
                           "source_id": "source:one"}], "source_id_match_status": "matched"}
        base = {"@type": "FeedbackLoopOutcome", "profile_id": "person:fixture:one", "source_id": "source:one",
            "outcome_status": "candidate_results", "result_source_document_ids": ["doc:result"],
            "result_source_documents_catalog": catalog,
            "search_memory_update_preview": {"profile_id": "person:fixture:one",
                "result_source_document_ids": ["doc:result"], "result_source_documents_catalog": catalog}}
        valid = self.root / "valid-result-attribution.json"
        valid.write_text(json.dumps(base), encoding="utf-8")
        valid_view = build_research_memory_view(inventory_path=inventory,
            output_dir=self.root / "view-valid-result-attribution", feedback_outcome_paths=[valid])
        self.assertEqual(valid_view["feedback_outcomes"][0]["result_source_attribution_status"], "matched")
        valid_markdown = (self.root / "view-valid-result-attribution" / "research-memory-view.md").read_text(encoding="utf-8")
        self.assertIn("Result source attribution: `matched`", valid_markdown)
        invalid_cases = [
            (lambda payload: (payload.update(result_source_document_ids=["doc:result", "doc:result"]),
                payload["search_memory_update_preview"].update(result_source_document_ids=["doc:result", "doc:result"])),
                "Invalid FeedbackLoopOutcome result_source_document_ids"),
            (lambda payload: (payload.update(result_source_document_ids=["doc:other"]),
                payload["search_memory_update_preview"].update(result_source_document_ids=["doc:other"])),
                "does not match result document IDs"),
            (lambda payload: payload["search_memory_update_preview"].update(result_source_document_ids=["doc:other"]), "Conflicting FeedbackLoopOutcome result document IDs"),
            (lambda payload: (payload["result_source_documents_catalog"].update(sha256="bad"),
                payload["search_memory_update_preview"]["result_source_documents_catalog"].update(sha256="bad")),
                "Invalid FeedbackLoopOutcome result catalog metadata"),
            (lambda payload: (payload["result_source_documents_catalog"].update(documents=[]),
                payload["search_memory_update_preview"]["result_source_documents_catalog"].update(documents=[])),
                "does not match result document IDs"),
            (lambda payload: (payload.update(result_source_document_ids=[]),
                payload["search_memory_update_preview"].update(result_source_document_ids=[])),
                "does not match result document IDs"),
            (lambda payload: (payload.update(result_source_documents_catalog="unverified"),
                payload["search_memory_update_preview"].update(result_source_documents_catalog="unverified")),
                "Invalid FeedbackLoopOutcome result catalog metadata"),
            (lambda payload: (payload["result_source_documents_catalog"].update(source_id_match_status="unknown"),
                payload["search_memory_update_preview"]["result_source_documents_catalog"].update(source_id_match_status="unknown")),
                "Invalid FeedbackLoopOutcome result source attribution status"),
            (lambda payload: (payload["result_source_documents_catalog"].update(source_id_match_status="matched"),
                payload["search_memory_update_preview"]["result_source_documents_catalog"].update(source_id_match_status="matched"),
                payload["result_source_documents_catalog"]["documents"][0].update(source_id="source:other"),
                payload["search_memory_update_preview"]["result_source_documents_catalog"]["documents"][0].update(source_id="source:other")),
                "conflicts with source_id"),
            (lambda payload: (payload["result_source_documents_catalog"].update(source_id_match_status="unavailable"),
                payload["search_memory_update_preview"]["result_source_documents_catalog"].update(source_id_match_status="unavailable")),
                "Invalid unavailable FeedbackLoopOutcome result source attribution"),
        ]
        outcome = self.root / "invalid-result-binding.json"
        for index, (mutate, message) in enumerate(invalid_cases):
            with self.subTest(index=index):
                payload = json.loads(json.dumps(base))
                mutate(payload)
                outcome.write_text(json.dumps(payload), encoding="utf-8")
                output_dir = self.root / f"invalid-result-view-{index}"
                with self.assertRaisesRegex(ValueError, message):
                    build_research_memory_view(inventory_path=inventory, output_dir=output_dir,
                        feedback_outcome_paths=[outcome])
                self.assertFalse(output_dir.exists())

    def test_view_includes_unreviewed_lineage_and_quote_status_as_diagnostics(self):
        inventory = self.inventory()
        lineage = self.root / "lineage.json"
        lineage.write_text(json.dumps({"@type": "CandidateSourceDocumentLineageSet", "preview_only": True,
            "links": [{"source_document_id": "local:1", "related_source_document_id": "online:1",
                "relation_type": "local_capture_of", "review_status": "unreviewed"}]}), encoding="utf-8")
        quotes = self.root / "quotes.json"
        quotes.write_text(json.dumps({"@type": "CandidateEvidenceQuoteVerification", "preview_only": True,
            "claims": [{"claim_id": "claim:1", "source_document_id": "local:1", "field": "formation.name",
                        "evidence_span": "Milito nella formazione.", "status": "not_exact"}]}), encoding="utf-8")
        output_dir = self.root / "view"
        view = build_research_memory_view(inventory_path=inventory, output_dir=output_dir,
            lineage_paths=[lineage], quote_verification_paths=[quotes])
        self.assertEqual(view["source_document_lineage"][0]["review_status"], "unreviewed")
        self.assertEqual(view["evidence_quote_checks"][0]["status"], "not_exact")
        self.assertEqual(view["source_document_lineage"][0]["lineage_artifact"], str(lineage.resolve()))
        self.assertEqual(view["source_document_lineage"][0]["lineage_sha256"], hashlib.sha256(lineage.read_bytes()).hexdigest())
        self.assertEqual(view["evidence_quote_checks"][0]["verification_artifact"], str(quotes.resolve()))
        self.assertEqual(view["evidence_quote_checks"][0]["verification_sha256"], hashlib.sha256(quotes.read_bytes()).hexdigest())
        persisted_view = json.loads((output_dir / "research-memory-view.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted_view, view)
        self.assertFalse(view["claim_promotion_allowed"])
        markdown = (output_dir / "research-memory-view.md").read_text(encoding="utf-8")
        self.assertIn("`not_exact`", markdown)
        self.assertIn("SourceDocument `local:1`", markdown)
        self.assertIn("`formation.name`", markdown)
        self.assertIn("Evidence: `Milito nella formazione.`", markdown)
        self.assertIn(str(quotes.resolve()), markdown)
        self.assertIn(hashlib.sha256(quotes.read_bytes()).hexdigest(), markdown)


if __name__ == "__main__":
    unittest.main()
