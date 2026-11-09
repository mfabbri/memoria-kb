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


def create_catalog(root):
    path = root / "catalog.sqlite"
    if not path.exists():
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE source_documents (document_id TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO source_documents VALUES ('document:synthetic')")
            connection.commit()
    return path


def write_claims(path, claims):
    path.write_text(json.dumps({"@type": "CandidateEvidenceClaimSet", "candidate_evidence_claims": claims}), encoding="utf-8")


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
    def test_catalog_change_after_preview_or_during_review_prevents_receipt(self):
        for change_during_review in (False, True):
            with self.subTest(change_during_review=change_during_review), workspace_temp_dir() as root:
                _, manifest = prepare_preview(root)

                def change_catalog():
                    with closing(sqlite3.connect(root / "catalog.sqlite")) as connection:
                        connection.execute("INSERT INTO source_documents VALUES ('document:changed')")
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
            receipt = run_candidate_evidence_claim_review_wizard(
                manifest_json=manifest, input_fn=lambda _: next(answers), output_fn=displayed.append,
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
