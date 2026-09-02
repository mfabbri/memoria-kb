from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_demo_descriptor import (  # noqa: E402
    build_mvp_demo_aligned_ledger,
    build_mvp_demo_descriptor,
    render_mvp_demo_reconciliation_markdown,
)
from caduti_fonti_report.document_analysis.mvp_demo_reconciliation_markdown import (  # noqa: E402
    render_mvp_demo_reconciliation_markdown as isolated_reconciliation_renderer,
)


@contextmanager
def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_demo_run(data_root: Path, run_id: str = "golden-run") -> Path:
    run_dir = data_root / "risultati" / "runs" / run_id
    write_json(
        run_dir / "mvp_consolidated_review_ledger.json",
        {
            "@type": "MvpConsolidatedReviewLedger",
            "profiles": [
                {
                    "profile_id": "person:purocielo:andreoli-dino",
                    "canonical_name": "Andreoli Dino",
                    "documents": [
                        {
                            "source_document_id": "legacy_csv:a4ac96061a2381b5",
                            "source_id": "legacy_csv",
                        },
                        {
                            "source_document_id": "local_docx:4c2ad1d2ab937913",
                            "source_id": "local_docx",
                        },
                        {
                            "source_document_id": "partigiani_italia:b45553cd6b1673d8",
                            "source_id": "partigiani_italia",
                        },
                    ],
                    "candidate_evidence_claims": [
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "source_document_id": "legacy_csv:a4ac96061a2381b5",
                            "source_id": "legacy_csv",
                            "field": "death.place",
                            "value": "Purocielo",
                            "normalized_value": "purocielo",
                            "extraction_method": "legacy_csv_row",
                            "review_status": "accepted",
                        },
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "source_document_id": "local_docx:4c2ad1d2ab937913",
                            "source_id": "local_docx",
                            "field": "death.place",
                            "value": "Purocielo",
                            "normalized_value": "purocielo",
                            "extraction_method": "docx_segment",
                            "review_status": "accepted",
                        },
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "source_document_id": "partigiani_italia:b45553cd6b1673d8",
                            "source_id": "partigiani_italia",
                            "field": "birth.year",
                            "value": "1918",
                            "normalized_value": "1918",
                            "extraction_method": "online_detail_structured_fields",
                            "review_status": "unreviewed",
                        },
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "source_document_id": "local_docx:4c2ad1d2ab937913",
                            "source_id": "local_docx",
                            "field": "birth.year",
                            "value": "1919",
                            "normalized_value": "1919",
                            "extraction_method": "docx_segment",
                            "review_status": "unreviewed",
                        },
                        {
                            "profile_id": "person:purocielo:andreoli-dino",
                            "source_document_id": "source-document:out-of-scope",
                            "source_id": "other",
                            "field": "ignored",
                            "value": "ignored",
                        },
                    ],
                },
                {
                    "profile_id": "person:purocielo:balboni-william",
                    "canonical_name": "Balboni William",
                    "documents": [
                        {
                            "source_document_id": "partigiani_italia:b6b3c9e526723a27",
                            "source_id": "partigiani_italia",
                        }
                    ],
                    "candidate_evidence_claims": [
                        {
                            "profile_id": "person:purocielo:balboni-william",
                            "source_document_id": "partigiani_italia:b6b3c9e526723a27",
                            "source_id": "partigiani_italia",
                            "field": "death.place",
                            "value": "Purocielo",
                            "normalized_value": "purocielo",
                            "extraction_method": "online_detail_structured_fields",
                            "review_status": "accepted",
                        }
                    ],
                },
            ],
        },
    )
    review_dir = run_dir / "historian_review"
    write_json(review_dir / "review_queue.json", {"items": [{"item_id": "demo-review-1"}]})
    write_json(
        review_dir / "review_decisions_summary.json",
        {
            "decisions": [
                {
                    "item_id": "demo-review-1",
                    "selected_action": "confirm",
                    "decision_status": "accepted",
                }
            ]
        },
    )
    write_json(review_dir / "verified_facts.preview.json", {"fact_count": 1, "facts": [{"field": "death.place"}]})
    write_json(
        review_dir / "profile_patch.preview.json",
        {
            "patch_count": 1,
            "profile_patches": [
                {"profile_id": "person:purocielo:andreoli-dino", "operations": [{"op": "set", "path": "/verified_facts/death.place"}]}
            ],
        },
    )
    write_json(run_dir / "mvp_package_readiness.json", {"status": "preview"})
    return run_dir


class MvpDemoDescriptorTests(unittest.TestCase):
    def test_builds_preview_descriptor_and_reconciliation_table(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            data_root = tmp_dir / "data-root"
            run_dir = write_demo_run(data_root)
            output_json = data_root / "database" / "memoria_mvp_demo.active.json"
            output_md = run_dir / "mvp_demo_reconciliation_table.md"

            descriptor = build_mvp_demo_descriptor(
                data_root=data_root,
                run_id="golden-run",
                output_json=output_json,
                output_reconciliation_md=output_md,
            )
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(descriptor["@type"], "MemoriaMvpDemoDescriptor")
        self.assertEqual(persisted["contract_version"], "memoria_mvp_demo.v1")
        self.assertTrue(persisted["preview_only"])
        self.assertFalse(persisted["safety"]["applies_profile_patch"])
        self.assertEqual(persisted["run_id"], "golden-run")
        self.assertEqual(persisted["status"], "ready_for_internal_demo")
        self.assertEqual(persisted["review"]["substantive_decision_count"], 1)
        self.assertEqual(persisted["review"]["verified_fact_preview_count"], 1)
        self.assertEqual(persisted["review"]["profile_patch_preview_count"], 1)
        self.assertEqual(persisted["readiness"]["status"], "ready_for_internal_demo")
        self.assertEqual(persisted["readiness"]["error_count"], 0)
        self.assertTrue(persisted["readiness"]["checks"]["has_multi_source_reconciliation"])
        self.assertEqual(persisted["readiness"]["selected_source_families"], ["legacy_csv", "local_docx", "partigiani_italia"])
        self.assertEqual(persisted["readiness"]["covered_source_families"], ["legacy_csv", "local_docx", "partigiani_italia"])
        self.assertEqual(persisted["readiness"]["missing_source_families"], [])
        self.assertEqual(persisted["readiness"]["covered_document_count"], 4)
        self.assertEqual(persisted["readiness"]["missing_source_document_ids"], [])
        self.assertEqual(
            persisted["readiness"]["source_family_diagnostics"],
            [
                {
                    "source_family": "legacy_csv",
                    "coverage_status": "covered",
                    "blocking_reason": "covered",
                    "selected_document_count": 1,
                    "covered_document_count": 1,
                    "missing_document_count": 0,
                },
                {
                    "source_family": "local_docx",
                    "coverage_status": "covered",
                    "blocking_reason": "covered",
                    "selected_document_count": 1,
                    "covered_document_count": 1,
                    "missing_document_count": 0,
                },
                {
                    "source_family": "partigiani_italia",
                    "coverage_status": "covered",
                    "blocking_reason": "covered",
                    "selected_document_count": 2,
                    "covered_document_count": 2,
                    "missing_document_count": 0,
                },
            ],
        )
        self.assertEqual(
            persisted["readiness"]["document_diagnostics"][0],
            {
                "source_document_id": "legacy_csv:a4ac96061a2381b5",
                "source_family": "legacy_csv",
                "reconciliation_status": "covered",
                "profile_scope_status": "present_in_selected_profiles",
                "candidate_claim_status": "claims_in_selected_profiles",
                "blocking_reason": "covered",
            },
        )
        self.assertEqual(
            persisted["readiness"]["next_actions"],
            ["Verificare review, verified facts preview e ProfilePatch preview prima di creare il descrittore T30."],
        )
        self.assertEqual(persisted["readiness"]["alignment_plan"], [])
        self.assertEqual(persisted["reconciliation"]["row_count"], 5)
        self.assertEqual(persisted["reconciliation"]["compatibility_counts"]["corroborated"], 2)
        self.assertEqual(persisted["reconciliation"]["compatibility_counts"]["divergent"], 2)
        self.assertEqual(persisted["reconciliation"]["compatibility_counts"]["single_source"], 1)
        self.assertIn("legacy_csv", persisted["source_families"])
        self.assertIn("local_docx", persisted["source_families"])
        self.assertIn("partigiani_italia", persisted["source_families"])
        self.assertIn("MVP demo reconciliation table", markdown)
        self.assertIn("Readiness: `ready_for_internal_demo`", markdown)
        self.assertIn("death.place", markdown)
        self.assertIn("corroborated", markdown)
        self.assertIn("divergent", markdown)

    def test_without_output_paths_returns_payload_without_writing_demo_files(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            data_root = tmp_dir / "data-root"
            run_dir = write_demo_run(data_root)

            descriptor = build_mvp_demo_descriptor(data_root=data_root, run_id="golden-run")
            markdown = render_mvp_demo_reconciliation_markdown(descriptor)

            descriptor_path_exists = (data_root / "database" / "memoria_mvp_demo.active.json").exists()
            reconciliation_path_exists = (run_dir / "mvp_demo_reconciliation_table.md").exists()

        self.assertEqual(descriptor["reconciliation"]["row_count"], 5)
        self.assertFalse(descriptor_path_exists)
        self.assertFalse(reconciliation_path_exists)
        self.assertIs(render_mvp_demo_reconciliation_markdown, isolated_reconciliation_renderer)

    def test_readiness_blocks_single_source_reconciliation(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            data_root = tmp_dir / "data-root"
            write_demo_run(data_root)

            descriptor = build_mvp_demo_descriptor(
                data_root=data_root,
                run_id="golden-run",
                source_document_id=["partigiani_italia:b45553cd6b1673d8"],
            )
            markdown = render_mvp_demo_reconciliation_markdown(descriptor)

        readiness = descriptor["readiness"]
        self.assertEqual(readiness["status"], "blocked_for_internal_demo")
        self.assertEqual(readiness["error_count"], 1)
        self.assertIn("multi_source_reconciliation_requires_at_least_two_source_families", readiness["errors"])
        self.assertFalse(readiness["checks"]["has_multi_source_reconciliation"])
        self.assertEqual(readiness["selected_source_families"], ["partigiani_italia"])
        self.assertEqual(readiness["covered_source_families"], ["partigiani_italia"])
        self.assertEqual(readiness["missing_source_families"], [])
        self.assertEqual(
            readiness["next_actions"],
            ["Aggiungere alla riconciliazione della run canonica claim da una seconda famiglia fonte T29."],
        )
        self.assertIn("- ERROR: multi_source_reconciliation_requires_at_least_two_source_families", markdown)
        self.assertIn("Azioni successive:", markdown)
        self.assertIn("Aggiungere alla riconciliazione della run canonica claim da una seconda famiglia fonte T29.", markdown)
        self.assertIn("Famiglie T29:", markdown)
        self.assertIn("| partigiani_italia | covered | covered | 1 | 1 | 0 |", markdown)
        self.assertIn("Documenti T29:", markdown)
        self.assertIn(
            "| partigiani_italia:b45553cd6b1673d8 | partigiani_italia | covered | "
            "present_in_selected_profiles | claims_in_selected_profiles | covered |",
            markdown,
        )
        self.assertNotIn("Piano riallineamento preview:", markdown)

    def test_readiness_explains_missing_selected_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            data_root = tmp_dir / "data-root"
            run_dir = write_demo_run(data_root)
            ledger_path = run_dir / "mvp_consolidated_review_ledger.json"
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            andreoli = ledger["profiles"][0]
            andreoli["candidate_evidence_claims"] = [
                claim
                for claim in andreoli["candidate_evidence_claims"]
                if claim.get("source_document_id")
                not in {"legacy_csv:a4ac96061a2381b5", "local_docx:4c2ad1d2ab937913"}
            ]
            ledger["profiles"].append(
                {
                    "profile_id": "person:purocielo:bendini-ateo",
                    "canonical_name": "Bendini Ateo",
                    "documents": [
                        {
                            "source_document_id": "local_docx:4c2ad1d2ab937913",
                            "source_id": "local_docx",
                        }
                    ],
                    "candidate_evidence_claims": [
                        {
                            "source_document_id": "local_docx:4c2ad1d2ab937913",
                            "source_id": "local_docx",
                            "field": "death.place",
                            "value": "Purocielo",
                        }
                    ],
                }
            )
            ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")

            descriptor = build_mvp_demo_descriptor(data_root=data_root, run_id="golden-run")
            markdown = render_mvp_demo_reconciliation_markdown(descriptor)

        readiness = descriptor["readiness"]
        self.assertIn("legacy_csv:a4ac96061a2381b5", readiness["missing_source_document_ids"])
        self.assertIn("local_docx:4c2ad1d2ab937913", readiness["missing_source_document_ids"])
        self.assertEqual(
            readiness["missing_documents_present_in_selected_profiles"],
            ["legacy_csv:a4ac96061a2381b5", "local_docx:4c2ad1d2ab937913"],
        )
        self.assertEqual(readiness["missing_documents_absent_from_selected_profiles"], [])
        self.assertEqual(readiness["missing_documents_without_candidate_claims"], ["legacy_csv:a4ac96061a2381b5"])
        self.assertEqual(
            readiness["missing_documents_with_claims_outside_selected_profiles"],
            ["local_docx:4c2ad1d2ab937913"],
        )
        diagnostics_by_document = {item["source_document_id"]: item for item in readiness["document_diagnostics"]}
        diagnostics_by_family = {item["source_family"]: item for item in readiness["source_family_diagnostics"]}
        self.assertEqual(diagnostics_by_family["legacy_csv"]["coverage_status"], "missing_reconciliation")
        self.assertEqual(diagnostics_by_family["local_docx"]["coverage_status"], "missing_reconciliation")
        self.assertEqual(diagnostics_by_family["partigiani_italia"]["coverage_status"], "covered")
        self.assertEqual(diagnostics_by_family["legacy_csv"]["blocking_reason"], "candidate_claims_missing")
        self.assertEqual(diagnostics_by_family["local_docx"]["blocking_reason"], "claims_outside_demo_scope")
        self.assertEqual(diagnostics_by_family["partigiani_italia"]["blocking_reason"], "covered")
        self.assertEqual(
            diagnostics_by_document["legacy_csv:a4ac96061a2381b5"]["candidate_claim_status"],
            "no_candidate_claims",
        )
        self.assertEqual(
            diagnostics_by_document["legacy_csv:a4ac96061a2381b5"]["blocking_reason"],
            "candidate_claims_missing",
        )
        self.assertEqual(
            diagnostics_by_document["local_docx:4c2ad1d2ab937913"]["candidate_claim_status"],
            "claims_outside_selected_profiles",
        )
        self.assertEqual(
            diagnostics_by_document["local_docx:4c2ad1d2ab937913"]["blocking_reason"],
            "claims_outside_demo_scope",
        )
        self.assertEqual(
            diagnostics_by_document["local_docx:4c2ad1d2ab937913"]["profile_scope_status"],
            "present_in_selected_profiles",
        )
        self.assertEqual(
            readiness["alignment_plan"],
            [
                {
                    "step": 1,
                    "action": "produce_candidate_claims",
                    "source_document_id": "legacy_csv:a4ac96061a2381b5",
                    "source_family": "legacy_csv",
                    "reason": "candidate_claims_missing",
                    "preview_only": True,
                    "target": "mvp_consolidated_review_ledger",
                },
                {
                    "step": 2,
                    "action": "attach_existing_claims_to_demo_profile",
                    "source_document_id": "local_docx:4c2ad1d2ab937913",
                    "source_family": "local_docx",
                    "reason": "claims_outside_demo_scope",
                    "preview_only": True,
                    "target": "mvp_consolidated_review_ledger",
                },
            ],
        )
        self.assertIn(
            "Produrre claim candidati nel ledger per i documenti selezionati senza claim: legacy_csv:a4ac96061a2381b5.",
            readiness["next_actions"],
        )
        self.assertIn(
            "Ricondurre al profilo demo selezionato i claim gia' presenti fuori perimetro per: local_docx:4c2ad1d2ab937913.",
            readiness["next_actions"],
        )
        self.assertIn("Piano riallineamento preview:", markdown)
        self.assertIn(
            "| 1 | produce_candidate_claims | legacy_csv:a4ac96061a2381b5 | legacy_csv | candidate_claims_missing |",
            markdown,
        )
        self.assertIn(
            "| 2 | attach_existing_claims_to_demo_profile | local_docx:4c2ad1d2ab937913 | local_docx | claims_outside_demo_scope |",
            markdown,
        )

    def test_aligned_ledger_sidecar_adds_preview_claims_for_t30_scope(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            data_root = tmp_dir / "data-root"
            run_dir = write_demo_run(data_root)
            ledger_path = run_dir / "mvp_consolidated_review_ledger.json"
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            andreoli = ledger["profiles"][0]
            andreoli["candidate_evidence_claims"] = [
                claim
                for claim in andreoli["candidate_evidence_claims"]
                if claim.get("source_document_id")
                not in {"legacy_csv:a4ac96061a2381b5", "local_docx:4c2ad1d2ab937913"}
            ]
            ledger["profiles"].append(
                {
                    "profile_id": "person:purocielo:bendini-ateo",
                    "canonical_name": "Bendini Ateo",
                    "documents": [{"source_document_id": "local_docx:4c2ad1d2ab937913", "source_id": "local_docx"}],
                    "candidate_evidence_claims": [
                        {
                            "@id": "candidate-evidence-claim:outside-local",
                            "profile_id": "person:purocielo:bendini-ateo",
                            "source_document_id": "local_docx:4c2ad1d2ab937913",
                            "source_id": "local_docx",
                            "field": "formation.name",
                            "value": "36a Brigata Garibaldi",
                            "normalized_value": "36a brigata garibaldi",
                            "extraction_method": "document_entity_context_rules",
                            "review_status": "unreviewed",
                        }
                    ],
                }
            )
            ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
            output_ledger = run_dir / "mvp_consolidated_review_ledger.t30-preview.json"

            aligned = build_mvp_demo_aligned_ledger(
                data_root=data_root,
                run_id="golden-run",
                output_json=output_ledger,
            )
            descriptor = build_mvp_demo_descriptor(data_root=data_root, run_id="golden-run", ledger_json=output_ledger)
            output_ledger_exists = output_ledger.exists()

        andreoli_claims = aligned["profiles"][0]["candidate_evidence_claims"]
        claim_by_document = {claim["source_document_id"]: claim for claim in andreoli_claims}
        self.assertTrue(output_ledger_exists)
        self.assertEqual(aligned["t30_alignment"]["added_candidate_claim_count"], 2)
        self.assertEqual(claim_by_document["legacy_csv:a4ac96061a2381b5"]["field"], "identity.canonical_name")
        self.assertEqual(claim_by_document["legacy_csv:a4ac96061a2381b5"]["review_status"], "unreviewed")
        self.assertEqual(claim_by_document["legacy_csv:a4ac96061a2381b5"]["alignment_status"], "t30_preview_candidate")
        self.assertEqual(claim_by_document["local_docx:4c2ad1d2ab937913"]["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(
            claim_by_document["local_docx:4c2ad1d2ab937913"]["alignment_source_profile_id"],
            "person:purocielo:bendini-ateo",
        )
        self.assertEqual(descriptor["readiness"]["status"], "ready_for_internal_demo")
        self.assertEqual(descriptor["readiness"]["alignment_plan"], [])
        self.assertEqual(descriptor["readiness"]["missing_source_document_ids"], [])

    def test_markdown_handles_empty_reconciliation(self) -> None:
        markdown = render_mvp_demo_reconciliation_markdown(
            {
                "contract_version": "memoria_mvp_demo.v1",
                "run_id": "golden-run",
                "primary_profile_ids": ["person:purocielo:andreoli-dino"],
                "contrast_profile_ids": [],
                "source_families": [],
                "reconciliation": {"rows": []},
            }
        )

        self.assertIn("preview_only: true", markdown)
        self.assertIn("_Nessun claim selezionato nel ledger._", markdown)


if __name__ == "__main__":
    unittest.main()
