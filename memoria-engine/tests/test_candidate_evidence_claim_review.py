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

from caduti_fonti_report.document_analysis.candidate_evidence_claim_review import (  # noqa: E402
    build_candidate_evidence_claim_review,
    run_candidate_evidence_claim_review_wizard,
)


@contextmanager
def workspace_temp_dir():
    base = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base.mkdir(exist_ok=True)
    root = base / f"claim-review-{uuid.uuid4().hex}"
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def claim(**updates):
    result = {"@type": "CandidateEvidenceClaim", "@id": "claim:synthetic",
              "profile_id": "person:synthetic", "source_id": "source:synthetic",
              "source_document_id": "document:synthetic", "field": "birth.municipality", "value": "Comune sintetico",
              "normalized_value": "comune sintetico", "review_status": "unreviewed", "confidence": 0.8,
              "extraction_method": "synthetic_fixture", "evidence_span": "Nato a Comune sintetico.",
              "context": "Estratto sintetico: Nato a Comune sintetico.",
              "provenance": {"source_url": "https://example.invalid/person", "page": 2}}
    result.update(updates)
    return result


def create_catalog(root, *, source_id=None):
    path = root / "catalog.sqlite"
    if not path.exists():
        with closing(sqlite3.connect(path)) as connection:
            if source_id is None:
                connection.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY, title TEXT, url TEXT)")
                connection.execute("INSERT INTO source_documents VALUES ('document:synthetic', 'Scheda sintetica', 'https://example.invalid/catalog-document')")
            else:
                connection.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY, title TEXT, url TEXT, source_id TEXT)")
                connection.execute("INSERT INTO source_documents VALUES ('document:synthetic', 'Scheda sintetica', 'https://example.invalid/catalog-document', ?)",
                    (source_id,))
            connection.commit()
    return path


def write_claims(path, claims):
    path.write_text(json.dumps({"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": claims}), encoding="utf-8")


def write_quote_verification(root, claims_path, claims, statuses):
    text_inputs = []
    for source_document_id in sorted({item["source_document_id"] for item in claims}):
        text_path = root / ("processed-" + str(len(text_inputs)) + ".json")
        document_claims = [item for item in claims if item["source_document_id"] == source_document_id]
        text = " ".join(item["evidence_span"] for item in document_claims
                         if statuses[item["@id"]] == "exact_match")
        text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        text_payload = {"@type": "ProcessedDocumentText", "source_id": document_claims[0]["source_id"],
                        "source_document_id": source_document_id,
                        "text": text, "text_sha256": text_sha256}
        text_path.write_text(json.dumps(text_payload), encoding="utf-8")
        raw = text_path.read_bytes()
        text_inputs.append({"path": str(text_path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
                            "source_document_id": source_document_id, "text_sha256": text_sha256})
    payload = {"@type": "CandidateEvidenceQuoteVerification", "schema_version": "1.0", "preview_only": True,
               "claims_input": {"path": str(claims_path.resolve()),
                                "sha256": hashlib.sha256(claims_path.read_bytes()).hexdigest()},
               "processed_text_inputs": text_inputs,
               "claims": [{"claim_id": item["@id"], "source_id": item["source_id"],
                           "source_document_id": item["source_document_id"], "evidence_span": item["evidence_span"],
                           "status": statuses[item["@id"]]} for item in claims],
               "status_counts": {status: list(statuses.values()).count(status) for status in sorted(set(statuses.values()))},
               "claim_count": len(claims)}
    path = root / "quote-verification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class CandidateEvidenceClaimReviewTests(unittest.TestCase):
    def test_output_cannot_create_a_catalog_sidecar_directory(self):
        with workspace_temp_dir() as root:
            source = root / "claims.json"
            write_claims(source, [claim()])
            database = create_catalog(root)
            before = database.read_bytes()
            reserved = Path(str(database) + "-wal")
            with self.assertRaises(ValueError):
                build_candidate_evidence_claim_review(
                    claims_json=source, source_documents_db=database, output_dir=reserved / "preview",
                )
            self.assertFalse(reserved.exists())
            self.assertEqual(database.read_bytes(), before)

    def test_catalog_missing_table_or_document_fails_before_output(self):
        for scenario in ("missing", "table", "document", "spaced-id"):
            with self.subTest(scenario=scenario), workspace_temp_dir() as root:
                source = root / "claims.json"
                write_claims(source, [claim(source_document_id=" document:synthetic" if scenario == "spaced-id" else "document:synthetic")])
                database = root / "catalog.sqlite"
                if scenario != "missing":
                    with closing(sqlite3.connect(database)) as connection:
                        if scenario == "table":
                            connection.execute("CREATE TABLE unrelated (id TEXT)")
                        else:
                            connection.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY)")
                            if scenario == "spaced-id":
                                connection.execute("INSERT INTO source_documents VALUES ('document:synthetic')")
                        connection.commit()
                before = database.read_bytes() if database.exists() else None
                with self.assertRaises(ValueError):
                    build_candidate_evidence_claim_review(claims_json=source, source_documents_db=database, output_dir=root / "preview")
                self.assertFalse((root / "preview").exists())
                self.assertEqual(database.read_bytes() if database.exists() else None, before)

    def test_binds_exact_input_and_outputs_preserving_provenance_without_decisions(self):
        with workspace_temp_dir() as root:
            source = root / "claims.json"
            original = claim()
            write_claims(source, [original])
            before = source.read_bytes()
            output = root / "preview"
            manifest = build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=output)
            queue = json.loads((output / "candidate_claim_review_queue.json").read_text(encoding="utf-8"))
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(manifest["claims_input"]["sha256"], hashlib.sha256(before).hexdigest())
            for reference in manifest["artifacts"].values():
                self.assertEqual(reference["sha256"], hashlib.sha256(Path(reference["path"]).read_bytes()).hexdigest())
            self.assertEqual(queue["items"][0]["source_claim"], original)
            self.assertEqual(queue["items"][0]["source_document_id"], "document:synthetic")
            self.assertEqual(queue["items"][0]["review_status"], "unreviewed")
            self.assertNotIn("decision", queue["items"][0])
            for key in ("decisions_recorded", "human_review_recorded", "claim_promotion_allowed", "canonical_write_allowed", "profile_write_allowed"):
                self.assertIs(manifest[key], False)
                self.assertIs(queue[key], False)
            self.assertIs(manifest["source_document_existence_verified"], True)
            self.assertEqual(manifest["source_documents_catalog"]["resolved_document_ids"], ["document:synthetic"])

    def test_quote_verification_is_hash_bound_and_visible_but_diagnostic_only(self):
        with workspace_temp_dir() as root:
            claims = [claim(**{"@id": "claim:exact"}),
                      claim(**{"@id": "claim:not-exact", "source_document_id": "document:second"})]
            source = root / "claims.json"
            write_claims(source, claims)
            database = create_catalog(root)
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("INSERT INTO source_documents VALUES ('document:second', 'Second fixture', '')")
                connection.commit()
            quote_path = write_quote_verification(root, source, claims,
                {"claim:exact": "exact_match", "claim:not-exact": "not_exact"})
            output = root / "preview-with-quotes"
            manifest = build_candidate_evidence_claim_review(
                claims_json=source, source_documents_db=database, output_dir=output,
                quote_verification_path=quote_path,
            )
            queue = json.loads((output / "candidate_claim_review_queue.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "1.3")
            self.assertEqual(manifest["quote_verification"]["sha256"], hashlib.sha256(quote_path.read_bytes()).hexdigest())
            self.assertEqual([item["evidence_quote_status"] for item in queue["items"]], ["exact_match", "not_exact"])
            self.assertIn("Quote verification: `not_exact` (diagnostic only)",
                          (output / "candidate_claim_review_queue.md").read_text(encoding="utf-8"))
            answers = iter(["reviewer-fixture", "a", "", "e", "Serve una fonte indipendente.", "s"])
            displayed = []
            receipt = run_candidate_evidence_claim_review_wizard(
                manifest_json=output / "candidate_claim_review_manifest.json",
                input_fn=lambda _: next(answers), output_fn=displayed.append,
            )
            self.assertEqual([item["evidence_quote_status"] for item in receipt["decisions"]],
                             ["exact_match", "not_exact"])
            self.assertTrue(any("not_exact (diagnostica" in line for line in displayed))
            self.assertFalse(receipt["claim_promotion_allowed"])
            self.assertFalse(receipt["canonical_write_allowed"])

    def test_quote_verification_rejects_hash_id_and_text_drift_before_output(self):
        for scenario in ("claims-hash", "claim-coverage", "duplicate-id", "forged-status", "processed-text-hash"):
            with self.subTest(scenario=scenario), workspace_temp_dir() as root:
                claims = [claim(**{"@id": "claim:one"}),
                          claim(**{"@id": "claim:two", "source_document_id": "document:second",
                                   "evidence_span": "Different evidence quote."})]
                source = root / "claims.json"
                write_claims(source, claims)
                database = create_catalog(root)
                with closing(sqlite3.connect(database)) as connection:
                    connection.execute("INSERT INTO source_documents VALUES ('document:second', 'Second fixture', '')")
                    connection.commit()
                quote_path = write_quote_verification(root, source, claims,
                    {"claim:one": "exact_match", "claim:two": "not_exact"})
                report = json.loads(quote_path.read_text(encoding="utf-8"))
                if scenario == "claims-hash":
                    report["claims_input"]["sha256"] = "0" * 64
                    quote_path.write_text(json.dumps(report), encoding="utf-8")
                elif scenario == "claim-coverage":
                    report["claims"] = report["claims"][:-1]
                    report["claim_count"] = len(report["claims"])
                    quote_path.write_text(json.dumps(report), encoding="utf-8")
                elif scenario == "duplicate-id":
                    report["claims"][1]["claim_id"] = report["claims"][0]["claim_id"]
                    quote_path.write_text(json.dumps(report), encoding="utf-8")
                elif scenario == "forged-status":
                    report["claims"][1]["status"] = "exact_match"
                    report["status_counts"] = {"exact_match": 2}
                    quote_path.write_text(json.dumps(report), encoding="utf-8")
                else:
                    text_path = Path(report["processed_text_inputs"][0]["path"])
                    text_path.write_text(text_path.read_text(encoding="utf-8") + " changed", encoding="utf-8")
                output = root / "invalid-preview"
                with self.assertRaises(ValueError):
                    build_candidate_evidence_claim_review(
                        claims_json=source, source_documents_db=database, output_dir=output,
                        quote_verification_path=quote_path,
                    )
                self.assertFalse(output.exists())

    def test_offline_cli_flow_preserves_quote_status_and_review_note_into_memory_view(self):
        with workspace_temp_dir() as root:
            launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
            source_claim = claim(**{"@id": "claim:e2e", "evidence_span": "Nato a Comune sintetico."})
            non_exact_claim = claim(**{
                "@id": "claim:e2e-not-exact", "field": "formation.name",
                "value": "Formazione sintetica", "normalized_value": "formazione sintetica",
                "evidence_span": "La formazione mai riportata nella scheda.",
                "context": "Estratto sintetico: La formazione mai riportata nella scheda.",
            })
            source_mismatch_claim = claim(**{
                "@id": "claim:e2e-source-mismatch", "source_id": "source:other",
                "field": "death.date", "value": "12 ottobre 1944",
                "normalized_value": "1944-10-12", "evidence_span": "12 ottobre 1944",
                "context": "Estratto sintetico: 12 ottobre 1944.",
            })
            missing_text_claim = claim(**{
                "@id": "claim:e2e-missing-text", "source_id": "source:second",
                "source_document_id": "document:second", "field": "birth.date",
                "value": "30 gennaio 1909", "normalized_value": "1909-01-30",
                "evidence_span": "30 gennaio 1909",
                "context": "Estratto sintetico: 30 gennaio 1909.",
            })
            claims_path = root / "claims.json"
            source_claims = [source_claim, non_exact_claim, source_mismatch_claim, missing_text_claim]
            write_claims(claims_path, source_claims)
            claims_before = claims_path.read_bytes()
            text = "Scheda sintetica. Nato a Comune sintetico."
            text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            processed_text = root / "processed-text.json"
            processed_text.write_text(json.dumps({
                "@type": "ProcessedDocumentText", "source_id": source_claim["source_id"],
                "source_document_id": source_claim["source_document_id"], "text": text,
                "text_sha256": text_sha256,
            }), encoding="utf-8")
            database = create_catalog(root, source_id=source_claim["source_id"])
            with closing(sqlite3.connect(database)) as connection:
                connection.execute(
                    "INSERT INTO source_documents (document_id, title, url, source_id) VALUES (?, ?, ?, ?)",
                    ("document:second", "Second synthetic sheet", "https://example.invalid/second", source_claim["source_id"]),
                )
                connection.commit()
            catalog_before = hashlib.sha256(database.read_bytes()).hexdigest()

            quote_dir = root / "quote-verification"
            verified = subprocess.run([
                str(launcher), "review", "evidence-verify", "--claims-json", str(claims_path),
                "--processed-text", str(processed_text), "--output-dir", str(quote_dir),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            quote_path = quote_dir / "quote-verification.json"
            quote_report = json.loads(quote_path.read_text(encoding="utf-8"))
            self.assertEqual(
                [item["status"] for item in quote_report["claims"]],
                ["exact_match", "not_exact", "source_id_mismatch", "missing_document_text"],
            )

            preview_dir = root / "preview"
            preview = subprocess.run([
                str(launcher), "review", "claims-preview", "--claims-json", str(claims_path),
                "--source-documents-db", str(database), "--quote-verification", str(quote_path),
                "--output-dir", str(preview_dir),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertIn("exact_match", preview.stdout)

            answers = iter([
                "reviewer-fixture", "e", "Serve una fonte indipendente.",
                "e", "La citazione proposta non compare nel testo acquisito.", "s",
                "e", "Verificare l'identificativo della fonte associata al testo.",
                "e", "Serve il testo acquisito del secondo documento.", "s",
            ])
            receipt = run_candidate_evidence_claim_review_wizard(
                manifest_json=preview_dir / "candidate_claim_review_manifest.json",
                input_fn=lambda _: next(answers), output_fn=lambda _: None,
                now_fn=lambda: datetime(2026, 11, 21, 12, 0, tzinfo=UTC),
            )
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")

            inventory_dir = root / "inventory"
            inventoried = subprocess.run([
                str(launcher), "review", "memory-inventory", "--receipt", str(receipt_path),
                "--output-dir", str(inventory_dir),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(inventoried.returncode, 0, inventoried.stderr)
            feedback_plan_path = root / "feedback-plan.json"
            feedback_plan_path.write_text(json.dumps({
                "@type": "FeedbackSearchPlanSet", "actions_sha256": "a" * 64,
                "review_status": "unreviewed", "execution_allowed": False,
                "online_search_started": False, "profile_write_allowed": False,
                "plans": [{
                    "@type": "FeedbackSearchPlan", "@id": "feedback-plan:e2e",
                    "feedback_search_plan_id": "feedback-plan:e2e",
                    "action_id": "feedback-action:e2e", "profile_id": source_claim["profile_id"],
                    "source_document_id": source_claim["source_document_id"],
                    "status": "ready_for_review", "manual_review_required": True,
                    "source_plans": [{
                        "@type": "FeedbackSearchSourcePlan", "source_id": source_claim["source_id"],
                        "status": "planned", "planned_attempts": [{
                            "query": "synthetic offline query", "strategy_id": "strategy:e2e",
                        }],
                    }],
                }],
            }), encoding="utf-8")
            outcome_specs = [
                ("candidate_results", ["--result-source-document-id", source_claim["source_document_id"]]),
                ("no_results", []),
                ("needs_manual_review", []),
                ("blocked_or_dynamic", []),
            ]
            feedback_paths = []
            generated_outcomes = []
            for index, (status, extra_args) in enumerate(outcome_specs):
                feedback_path = root / f"feedback-{status}.json"
                feedback_generated = subprocess.run([
                    str(launcher), "feedback", "outcome", "--feedback-plan-json", str(feedback_plan_path),
                    "--action-id", "feedback-action:e2e", "--plan-id", "feedback-plan:e2e",
                    "--source-id", source_claim["source_id"], "--strategy-id", "strategy:e2e",
                    "--outcome-status", status, "--query", "synthetic offline query",
                    "--run-id", f"run:e2e-feedback-{index}",
                    "--executed-at", f"2026-11-21T12:0{index}:00+00:00",
                    *extra_args, "--source-documents-db", str(database),
                    "--output-json", str(feedback_path),
                ], capture_output=True, text=True, check=False)
                self.assertEqual(feedback_generated.returncode, 0, feedback_generated.stderr)
                generated = json.loads(feedback_path.read_text(encoding="utf-8"))
                self.assertEqual(generated["outcome_status"], status)
                self.assertFalse(generated["profile_write_allowed"])
                self.assertFalse(generated["claim_promotion_allowed"])
                feedback_paths.append(feedback_path)
                generated_outcomes.append(generated)
            self.assertEqual(generated_outcomes[0]["result_source_document_ids"], [source_claim["source_document_id"]])
            self.assertEqual(generated_outcomes[0]["result_source_documents_catalog"]["resolved_document_ids"],
                [source_claim["source_document_id"]])
            self.assertEqual(generated_outcomes[0]["result_source_documents_catalog"]["source_id_match_status"], "matched")
            self.assertEqual(generated_outcomes[0]["result_source_documents_catalog"]["documents"][0]["source_id"],
                source_claim["source_id"])
            self.assertIn("no_results_is_search_memory_not_historical_absence_proof", generated_outcomes[1]["warnings"])
            view_dir = root / "memory-view"
            view_command = [
                str(launcher), "review", "memory-view", "--inventory-json",
                str(inventory_dir / "research-memory-inventory.json"), "--quote-verification", str(quote_path),
            ]
            for feedback_path in feedback_paths:
                view_command.extend(["--feedback-outcome", str(feedback_path)])
            view_command.extend(["--output-dir", str(view_dir)])
            viewed = subprocess.run(view_command, capture_output=True, text=True, check=False)
            self.assertEqual(viewed.returncode, 0, viewed.stderr)

            view = json.loads((view_dir / "research-memory-view.json").read_text(encoding="utf-8"))
            decisions = {item["claim_id"]: item for item in view["claim_decisions"]}
            self.assertEqual(decisions["claim:e2e"]["decision"], "needs_more_evidence")
            self.assertEqual(decisions["claim:e2e"]["note"], "Serve una fonte indipendente.")
            self.assertEqual(decisions["claim:e2e-not-exact"]["decision"], "needs_more_evidence")
            self.assertEqual(decisions["claim:e2e-not-exact"]["note"], "La citazione proposta non compare nel testo acquisito.")
            self.assertEqual(decisions["claim:e2e-source-mismatch"]["decision"], "needs_more_evidence")
            self.assertEqual(decisions["claim:e2e-source-mismatch"]["note"], "Verificare l'identificativo della fonte associata al testo.")
            self.assertEqual(decisions["claim:e2e-missing-text"]["decision"], "needs_more_evidence")
            self.assertEqual(decisions["claim:e2e-missing-text"]["note"], "Serve il testo acquisito del secondo documento.")
            quote_checks = {item["claim_id"]: item for item in view["evidence_quote_checks"]}
            self.assertEqual(quote_checks["claim:e2e"]["status"], "exact_match")
            self.assertEqual(quote_checks["claim:e2e-not-exact"]["status"], "not_exact")
            self.assertEqual(quote_checks["claim:e2e-source-mismatch"]["status"], "source_id_mismatch")
            self.assertEqual(quote_checks["claim:e2e-missing-text"]["status"], "missing_document_text")
            self.assertFalse(view["canonical_write_allowed"])
            self.assertFalse(view["claim_promotion_allowed"])
            feedback_outcomes = view["feedback_outcomes"]
            self.assertEqual([item["outcome_id"] for item in feedback_outcomes],
                [item["feedback_loop_outcome_id"] for item in generated_outcomes])
            self.assertEqual([item["outcome_status"] for item in feedback_outcomes],
                [status for status, _ in outcome_specs])
            self.assertEqual([item["warnings"] for item in feedback_outcomes],
                [item["warnings"] for item in generated_outcomes])
            self.assertEqual([item["path"] for item in feedback_outcomes],
                [str(path.resolve()) for path in feedback_paths])
            self.assertEqual([item["sha256"] for item in feedback_outcomes],
                [hashlib.sha256(path.read_bytes()).hexdigest() for path in feedback_paths])
            self.assertEqual(feedback_outcomes[0]["result_source_document_ids"],
                generated_outcomes[0]["result_source_document_ids"])
            self.assertEqual(feedback_outcomes[0]["result_source_attribution_status"], "matched")
            result_catalog = feedback_outcomes[0]["result_source_documents_catalog"]
            self.assertEqual(result_catalog, generated_outcomes[0]["result_source_documents_catalog"])
            self.assertEqual(result_catalog["path"], str(database.resolve()))
            self.assertEqual(result_catalog["sha256"], catalog_before)
            self.assertEqual(result_catalog["resolved_document_ids"], [source_claim["source_document_id"]])
            self.assertEqual(result_catalog["documents"][0]["title"], "Scheda sintetica")
            markdown = (view_dir / "research-memory-view.md").read_text(encoding="utf-8")
            for generated, path in zip(generated_outcomes, feedback_paths, strict=True):
                self.assertIn(generated["feedback_loop_outcome_id"], markdown)
                self.assertIn(generated["outcome_status"], markdown)
                self.assertIn(str(path.resolve()), markdown)
                self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), markdown)
            self.assertIn("no_results_is_search_memory_not_historical_absence_proof", markdown)
            self.assertIn(f"Result SourceDocument: `{source_claim['source_document_id']}`", markdown)
            self.assertIn("Result source attribution: `matched`", markdown)
            self.assertIn(str(database.resolve()), markdown)
            self.assertIn(catalog_before, markdown)
            self.assertIn("Serve una fonte indipendente.", markdown)
            self.assertIn("exact_match", markdown)
            self.assertIn("Nato a Comune sintetico.", markdown)
            self.assertIn("not_exact", markdown)
            self.assertIn("La formazione mai riportata nella scheda.", markdown)
            self.assertIn("source_id_mismatch", markdown)
            self.assertIn("missing_document_text", markdown)
            self.assertIn("SourceDocument `document:synthetic`", markdown)
            self.assertIn(str(quote_path.resolve()), markdown)
            self.assertIn(hashlib.sha256(quote_path.read_bytes()).hexdigest(), markdown)
            self.assertEqual(claims_path.read_bytes(), claims_before)
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), catalog_before)

    def test_idempotent_retry_is_byte_identical_and_divergent_retry_refused(self):
        with workspace_temp_dir() as root:
            source = root / "claims.json"
            write_claims(source, [claim()])
            output = root / "preview"
            first = build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=output)
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            self.assertEqual(build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=output), first)
            self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)
            write_claims(source, [claim(value="Altro comune")])
            with self.assertRaises(ValueError):
                build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=output)
            self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)

    def test_missing_provenance_and_non_candidate_claims_fail_before_output(self):
        mutations = [{key: ""} for key in ("@id", "profile_id", "source_id", "source_document_id", "field", "value", "extraction_method")]
        mutations += [{"review_status": status} for status in (None, "pending", "approved")]
        mutations += [{"confidence": value} for value in (None, True, -0.1, 1.1, float("nan"))]
        mutations += [{"evidence_span": "", "context": ""}, {"@type": "EvidenceClaim"}]
        for mutation in mutations:
            with self.subTest(mutation=mutation), workspace_temp_dir() as root:
                source = root / "claims.json"
                write_claims(source, [claim(**mutation)])
                with self.assertRaises(ValueError):
                    build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=root / "preview")
                self.assertFalse((root / "preview").exists())

    def test_duplicate_ids_and_non_object_claims_are_refused(self):
        for claims in ([claim(), copy.deepcopy(claim())], ["not-a-claim"]):
            with self.subTest(claims=claims), workspace_temp_dir() as root:
                source = root / "claims.json"
                write_claims(source, claims)
                with self.assertRaises(ValueError):
                    build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=root / "preview")

    def test_wrong_set_shape_and_output_overwrite_are_refused(self):
        for payload in ([], {"@type": "EvidenceClaimSet"}, {"@type": "CandidateEvidenceClaimSet"},
                        {"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": {}}):
            with self.subTest(payload=payload), workspace_temp_dir() as root:
                source = root / "claims.json"
                source.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(ValueError):
                    build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=root / "preview")
                self.assertFalse((root / "preview").exists())
        with workspace_temp_dir() as root:
            source = root / "claims.json"
            write_claims(source, [claim()])
            output = root / "preview"
            output.mkdir()
            existing = output / "user-note.md"
            existing.write_text("Preserve this note.", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=output)
            self.assertEqual(existing.read_text(encoding="utf-8"), "Preserve this note.")

    def test_person_candidate_id_is_explicit_fallback_and_context_can_supply_evidence(self):
        with workspace_temp_dir() as root:
            source = root / "claims.json"
            item = claim(profile_id="", person_candidate_id="person-candidate:synthetic", evidence_span="")
            write_claims(source, [item])
            build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=root / "preview")
            queue = json.loads((root / "preview" / "candidate_claim_review_queue.json").read_text(encoding="utf-8"))
            self.assertEqual(queue["items"][0]["profile_id"], "person-candidate:synthetic")
            self.assertEqual(queue["items"][0]["source_claim"], item)

    def test_installed_launcher_generates_preview_and_rejects_invalid_input(self):
        launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
        with workspace_temp_dir() as root:
            source = root / "claims.json"
            write_claims(source, [claim()])
            before = source.read_bytes()
            command = [str(launcher), "review", "claims-preview", "--claims-json", str(source),
                       "--source-documents-db", str(create_catalog(root)), "--output-dir", str(root / "preview")]
            missing_catalog = subprocess.run(
                [str(launcher), "review", "claims-preview", "--claims-json", str(source), "--output-dir", str(root / "preview")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(missing_catalog.returncode, 2)
            self.assertFalse((root / "preview").exists())
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("candidate_claim_review_manifest.json", completed.stdout)
            self.assertEqual(source.read_bytes(), before)
            manifest = json.loads((root / "preview" / "candidate_claim_review_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["counts"]["claims"], 1)
            quote_path = write_quote_verification(root, source, [claim()], {"claim:synthetic": "exact_match"})
            quote_output = root / "preview-with-quotes"
            quote_command = [str(launcher), "review", "claims-preview", "--claims-json", str(source),
                            "--source-documents-db", str(create_catalog(root)), "--quote-verification", str(quote_path),
                            "--output-dir", str(quote_output)]
            quote_result = subprocess.run(quote_command, capture_output=True, text=True, check=False)
            self.assertEqual(quote_result.returncode, 0, quote_result.stderr)
            self.assertIn("exact_match", quote_result.stdout)
            quote_manifest = json.loads((quote_output / "candidate_claim_review_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(quote_manifest["quote_status_counts"], {"exact_match": 1})
            write_claims(source, [claim(source_document_id="")])
            command[-1] = str(root / "invalid-preview")
            invalid = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(invalid.returncode, 1)
            self.assertIn("source_document_id", invalid.stderr)
            self.assertFalse((root / "invalid-preview").exists())


def prepare_preview(root, claims=None):
    source = root / "claims.json"
    write_claims(source, claims if claims is not None else [claim()])
    output = root / "preview"
    build_candidate_evidence_claim_review(claims_json=source, source_documents_db=create_catalog(root), output_dir=output)
    return source, output / "candidate_claim_review_manifest.json"


class CandidateEvidenceClaimReviewWizardTests(unittest.TestCase):
    def test_needs_more_evidence_requires_a_rationale_before_receipt(self):
        with workspace_temp_dir() as root:
            _, manifest = prepare_preview(root)
            answers = iter(["reviewer-fixture", "e", "", "La scheda non specifica l'unità di appartenenza.", "s"])
            prompts = []
            displayed = []
            receipt = run_candidate_evidence_claim_review_wizard(
                manifest_json=manifest,
                input_fn=lambda prompt: (prompts.append(prompt), next(answers))[1],
                output_fn=displayed.append,
            )
            self.assertIsNotNone(receipt)
            self.assertEqual(receipt["decisions"][0]["decision"], "needs_more_evidence")
            self.assertEqual(receipt["decisions"][0]["note"], "La scheda non specifica l'unità di appartenenza.")
            self.assertEqual(sum("Quale evidenza manca?" in prompt for prompt in prompts), 2)
            self.assertTrue(any("specifica quale informazione o fonte manca" in line for line in displayed))

    def test_legacy_v11_queue_remains_readable_after_v12_metadata_extension(self):
        with workspace_temp_dir() as root:
            _, manifest_path = prepare_preview(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = "1.1"
            queue_path = Path(manifest["artifacts"]["review_queue"]["path"])
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            for item in queue["items"]:
                item.pop("source_document_title", None)
                item.pop("source_document_url", None)
            queue_bytes = (json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
            queue_path.write_bytes(queue_bytes)
            manifest["artifacts"]["review_queue"]["sha256"] = hashlib.sha256(queue_bytes).hexdigest()
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            answers = iter(["reviewer-fixture", "a", "", "s"])
            receipt = run_candidate_evidence_claim_review_wizard(
                manifest_json=manifest_path, input_fn=lambda _: next(answers), output_fn=lambda _: None,
            )
            self.assertTrue(receipt["review_complete"])

    def test_catalog_change_after_preview_or_during_review_prevents_receipt(self):
        for change_during_review in (False, True):
            with self.subTest(change_during_review=change_during_review), workspace_temp_dir() as root:
                _, manifest = prepare_preview(root)

                def change_catalog():
                    with closing(sqlite3.connect(root / "catalog.sqlite")) as connection:
                        connection.execute("INSERT INTO source_documents (document_id) VALUES ('document:changed')")
                        connection.commit()

                if not change_during_review:
                    change_catalog()
                answers = iter(["fixture", "a", "", "s"])

                def answer(prompt, answers=answers):
                    if prompt.startswith("Confermare"):
                        change_catalog()
                    return next(answers)

                with self.assertRaises(ValueError):
                    run_candidate_evidence_claim_review_wizard(
                        manifest_json=manifest, input_fn=answer, output_fn=lambda _: None,
                    )

    def test_collects_each_claim_with_context_timestamps_and_exact_hash_binding(self):
        with workspace_temp_dir() as root:
            source, manifest = prepare_preview(root, [claim(**{"@id": f"claim:{index}"}) for index in range(3)])
            before = source.read_bytes()
            answers = iter(["reviewer-fixture", "a", "nota sintetica", "r", "", "e", "altra fonte", "s"])
            timestamps = iter([datetime(2026, 1, 1, 12, minute, tzinfo=UTC) for minute in range(3)])
            displayed = []
            prompts = []
            receipt = run_candidate_evidence_claim_review_wizard(
                manifest_json=manifest, input_fn=lambda prompt: (prompts.append(prompt), next(answers))[1], output_fn=displayed.append,
                now_fn=lambda: next(timestamps),
            )
            self.assertEqual(receipt["decision_counts"], {"accept_candidate": 1, "reject_candidate": 1, "needs_more_evidence": 1})
            self.assertEqual(receipt["preview_manifest"]["sha256"], hashlib.sha256(manifest.read_bytes()).hexdigest())
            queue_ref = receipt["preview_artifacts"]["review_queue"]
            self.assertEqual(queue_ref["sha256"], hashlib.sha256(Path(queue_ref["path"]).read_bytes()).hexdigest())
            self.assertEqual(source.read_bytes(), before)
            for index, decision in enumerate(receipt["decisions"]):
                self.assertEqual(decision["reviewed_at"], f"2026-01-01T12:0{index}:00+00:00")
                self.assertEqual(decision["reviewer"], "reviewer-fixture")
                self.assertEqual(decision["source_claim"]["provenance"]["source_url"], "https://example.invalid/person")
                self.assertEqual(decision["review_status"], "unreviewed")
            self.assertTrue(any("[1/3]" in line for line in displayed))
            self.assertTrue(any("Evidenza:" in line for line in displayed))
            self.assertTrue(any("https://example.invalid/person" in line for line in displayed))
            self.assertTrue(any("Scheda sintetica" in line for line in displayed))
            self.assertTrue(any("URL della scheda: https://example.invalid/catalog-document" in line for line in displayed))
            self.assertTrue(any("Profilo a cui il report propone" in line for line in displayed))
            self.assertTrue(any("comune di nascita" in line for line in displayed))
            self.assertTrue(any("[e] altra evidenza" in prompt for prompt in prompts))
            self.assertIs(receipt["decisions_recorded"], True)
            for key in ("claim_promotion_allowed", "canonical_write_allowed", "profile_write_allowed",
                        "person_identity_resolved", "reviewer_identity_authenticated"):
                self.assertIs(receipt[key], False)
            self.assertIs(receipt["source_document_existence_verified"], True)

    def test_cancel_or_unconfirmed_review_returns_no_receipt(self):
        for answers in (["q"], ["fixture", "q"], ["fixture", "a", "q"], ["fixture", "a", "", "n"], ["fixture", "a", "", ""]):
            with self.subTest(answers=answers), workspace_temp_dir() as root:
                source, manifest = prepare_preview(root)
                original = source.read_bytes()
                responses = iter(answers)
                receipt = run_candidate_evidence_claim_review_wizard(
                    manifest_json=manifest, input_fn=lambda _, responses=responses: next(responses), output_fn=lambda _: None,
                )
                self.assertIsNone(receipt)
                self.assertEqual(source.read_bytes(), original)

    def test_interrupted_review_does_not_return_a_receipt(self):
        for answers in ([KeyboardInterrupt()], ["fixture", "a", "", EOFError()]):
            with self.subTest(answers=answers), workspace_temp_dir() as root:
                _, manifest = prepare_preview(root)
                responses = iter(answers)

                def answer(_, responses=responses):
                    response = next(responses)
                    if isinstance(response, BaseException):
                        raise response
                    return response

                with self.assertRaises(type(answers[-1])):
                    run_candidate_evidence_claim_review_wizard(manifest_json=manifest, input_fn=answer, output_fn=lambda _: None)

    def test_tampered_input_queue_markdown_and_manifest_fail_before_prompt(self):
        for target in ("input", "queue", "markdown", "queue-with-updated-hash", "flags", "counts"):
            with self.subTest(target=target), workspace_temp_dir() as root:
                source, manifest = prepare_preview(root)
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if target == "input":
                    source.write_bytes(source.read_bytes() + b" ")
                elif target in {"queue", "markdown", "queue-with-updated-hash"}:
                    key = "review_markdown" if target == "markdown" else "review_queue"
                    path = Path(payload["artifacts"][key]["path"])
                    if target == "queue-with-updated-hash":
                        queue = json.loads(path.read_text(encoding="utf-8"))
                        queue["items"][0]["candidate"]["value"] = "Altered"
                        path.write_text(json.dumps(queue), encoding="utf-8")
                        payload["artifacts"][key]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                        manifest.write_text(json.dumps(payload), encoding="utf-8")
                    else:
                        path.write_bytes(path.read_bytes() + b" ")
                else:
                    if target == "flags":
                        payload["canonical_write_allowed"] = True
                    else:
                        payload["counts"]["claims"] = 2
                    manifest.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(ValueError):
                    run_candidate_evidence_claim_review_wizard(
                        manifest_json=manifest, input_fn=lambda _: self.fail("must validate before prompting"),
                    )

    def test_missing_reviewer_naive_clock_and_changed_input_fail(self):
        with workspace_temp_dir() as root:
            source, manifest = prepare_preview(root)
            with self.assertRaises(ValueError):
                run_candidate_evidence_claim_review_wizard(manifest_json=manifest, input_fn=lambda _: "", output_fn=lambda _: None)
            answers = iter(["fixture", "a"])
            with self.assertRaises(ValueError):
                run_candidate_evidence_claim_review_wizard(
                    manifest_json=manifest, input_fn=lambda _: next(answers), output_fn=lambda _: None,
                    now_fn=lambda: datetime(2026, 1, 1),
                )
            answers = iter(["fixture", "a", "", "s"])

            def answer(prompt):
                if prompt.startswith("Confermare"):
                    source.write_bytes(source.read_bytes() + b" ")
                return next(answers)

            with self.assertRaises(ValueError):
                run_candidate_evidence_claim_review_wizard(manifest_json=manifest, input_fn=answer, output_fn=lambda _: None)

    def test_installed_launcher_exposes_wizard_and_rejects_noninteractive_input(self):
        launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
        help_result = subprocess.run([str(launcher), "review", "claims-wizard", "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--manifest", help_result.stdout)
        with workspace_temp_dir() as root:
            _, manifest = prepare_preview(root)
            output = root / "receipt.json"
            result = subprocess.run([str(launcher), "review", "claims-wizard", "--manifest", str(manifest), "--output", str(output)],
                                    input="fixture\na\n\ns\n", capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("interactive terminal", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
