from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore  # noqa: E402


@contextmanager
def workspace_temp_dir():
    base_dir = ROOT_DIR / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def powershell_exe() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def run_memoria(shell: str, *args: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [
            shell,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT_DIR / "scripts" / "memoria.ps1"),
            *args,
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "memoria.ps1 failed\n"
            f"args={args}\n"
            f"stdout={completed.stdout}\n"
            f"stderr={completed.stderr}"
        )
    return completed


def run_memoria_raw(shell: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            shell,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT_DIR / "scripts" / "memoria.ps1"),
            *args,
        ],
        capture_output=True,
        text=True,
    )


def write_review_workspace(workspace: Path) -> tuple[Path, Path]:
    runs_dir = workspace / "risultati" / "runs"
    weak_run = runs_dir / "run-debole-pipeline"
    strong_run = runs_dir / "run-forte-pipeline"
    alternative_run = runs_dir / "run-alternativa-pipeline"
    profiles_dir = workspace / "ricerche" / "person_profiles"
    write_json(
        profiles_dir / "purocielo.index.jsonld",
        {
            "@type": "PersonResearchProfileIndex",
            "profiles": [
                {
                    "@id": "person:purocielo:test",
                    "file": "purocielo-test.jsonld",
                    "canonical_name": "Persona Test",
                }
            ],
        },
    )
    write_json(
        profiles_dir / "purocielo-test.jsonld",
        {
            "@type": "PersonResearchProfile",
            "profile_id": "person:purocielo:test",
            "canonical_name": "Persona Test",
            "birth": {},
            "evidence_claim_ids": [],
        },
    )
    write_json(
        weak_run / "historian_review" / "review_queue.json",
        {"items": [{"item_id": "review:item:weak"}]},
    )
    write_json(
        strong_run / "historian_review" / "review_queue.json",
        {
            "items": [
                {
                    "item_id": "review:item:1",
                    "profile_id": "person:purocielo:test",
                    "source_document_id": "source-document:test",
                    "source_item_id": "candidate:test:1",
                    "subject_kind": "claim",
                    "item_type": "candidate_claim_review",
                    "question": "Questo documento conferma il claim?",
                    "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                },
                {
                    "item_id": "review:item:2",
                    "profile_id": "person:purocielo:test",
                    "source_document_id": "source-document:test-2",
                    "source_item_id": "candidate:test:2",
                    "subject_kind": "document",
                    "item_type": "document_link_review",
                    "question": "Questo documento riguarda la persona?",
                    "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                },
            ]
        },
    )
    write_json(
        strong_run / "historian_review" / "review_decisions.template.json",
        {
            "@type": "MvpReviewDecisions",
            "decisions": [
                {"@type": "ReviewDecision", "item_id": "review:item:1", "selected_action": ""},
                {"@type": "ReviewDecision", "item_id": "review:item:2", "selected_action": ""},
            ],
        },
    )
    write_json(
        strong_run / "historian_review" / "review_decisions_summary.json",
        {
            "review_status": "pending_review",
            "pending_count": 2,
            "accepted_count": 0,
            "invalid_count": 0,
            "review_session": {"session_status": "not_started"},
            "decisions": [
                {
                    "decision_id": "decision:1",
                    "profile_id": "person:purocielo:test",
                    "source_document_id": "source-document:test",
                    "subject_kind": "claim",
                    "selected_action": "accept_for_search",
                    "decision_status": "accepted",
                }
            ],
        },
    )
    write_json(
        strong_run / "historian_review" / "review_session.json",
        {
            "profiles": [
                {
                    "profile_id": "person:purocielo:test",
                    "canonical_name": "Persona Test",
                    "pilot_card_status": "ready_for_review",
                    "model_card_review_status": "in_historical_review",
                    "review_session_status": "not_started",
                    "review_item_count": 2,
                    "pending_decision_count": 2,
                    "accepted_decision_count": 0,
                    "invalid_decision_count": 0,
                    "document_count": 2,
                    "candidate_evidence_claim_count": 1,
                    "reviewable_document_signal_count": 1,
                    "next_action": "Completare la review storica.",
                    "review_focus_items": [
                        {
                            "item_id": "review:item:1",
                            "subject_kind": "claim",
                            "item_type": "candidate_claim_review",
                            "question": "Questo documento conferma il claim?",
                            "source_document_id": "source-document:test",
                            "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                            "selected_action": "pending",
                            "decision_status": "pending",
                        }
                    ],
                }
            ],
            "review_focus": {
                "profiles": [
                    {
                        "profile_id": "person:purocielo:test",
                        "canonical_name": "Persona Test",
                        "items": [
                            {
                                "item_id": "review:item:1",
                                "subject_kind": "claim",
                                "item_type": "candidate_claim_review",
                                "question": "Questo documento conferma il claim?",
                                "source_document_id": "source-document:test",
                                "raw_file": "documenti_da_processare/purocielo/test.pdf",
                                "metadata_file": "documenti_processati/purocielo/test.metadata.json",
                                "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                                "selected_action": "pending",
                                "decision_status": "pending",
                            },
                            {
                                "item_id": "review:item:2",
                                "subject_kind": "document",
                                "item_type": "document_link_review",
                                "question": "Questo documento riguarda la persona?",
                                "source_document_id": "source-document:test-2",
                                "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                                "selected_action": "pending",
                                "decision_status": "pending",
                            },
                        ],
                    }
                ]
            },
        },
    )
    write_json(strong_run / "mvp_consolidated_review_ledger.json", {"profiles": [{"profile_id": "person:purocielo:test"}]})
    write_json(
        alternative_run / "historian_review" / "review_queue.json",
        {
            "items": [
                {
                    "item_id": "review:item:alt:1",
                    "profile_id": "person:purocielo:bagni-alfonso",
                    "source_document_id": "source-document:bagni",
                    "source_item_id": "candidate:bagni:1",
                    "subject_kind": "claim",
                    "item_type": "candidate_claim_review",
                    "question": "Questo documento conferma un dato su Bagni Alfonso?",
                    "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                }
            ]
        },
    )
    write_json(
        alternative_run / "historian_review" / "review_session.json",
        {
            "profiles": [
                {
                    "profile_id": "person:purocielo:bagni-alfonso",
                    "canonical_name": "Bagni Alfonso",
                    "review_session_status": "not_started",
                    "review_item_count": 1,
                    "pending_decision_count": 1,
                    "accepted_decision_count": 0,
                    "invalid_decision_count": 0,
                    "next_action": "Validare le evidenze candidate per Bagni Alfonso.",
                }
            ],
            "review_focus": {
                "profiles": [
                    {
                        "profile_id": "person:purocielo:bagni-alfonso",
                        "canonical_name": "Bagni Alfonso",
                        "items": [
                            {
                                "item_id": "review:item:alt:1",
                                "subject_kind": "claim",
                                "item_type": "candidate_claim_review",
                                "question": "Questo documento conferma un dato su Bagni Alfonso?",
                                "source_document_id": "source-document:bagni",
                                "selected_action": "pending",
                                "decision_status": "pending",
                            }
                        ],
                    }
                ]
            },
        },
    )
    database_dir = workspace / "database"
    database_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteEvidenceStore(database_dir / "evidence.sqlite")
    store.init_schema()
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:run-forte-pipeline",
            "source_run_id": "run-forte-pipeline",
            "imported_at": "2026-06-30T10:00:00+00:00",
            "source_run_dir": str(strong_run),
            "record_count": 2,
            "payload_hash": "batch-hash-review",
        }
    )
    for record in [
        {
            "record_id": "evidence-record:review-target-1",
            "record_kind": "review_queue_item",
            "subject_id": "person:purocielo:test",
            "source_document_id": "source-document:test",
            "review_status": "pending",
            "payload_hash": "record-hash-review-target-1",
            "payload": {
                "@type": "MvpReviewQueueItem",
                "item_id": "review:item:1",
                "item_type": "candidate_claim_review",
                "subject_kind": "claim",
                "decision_type": "candidate_claim",
                "profile_id": "person:purocielo:test",
                "canonical_name": "Persona Test",
                "source_item_id": "candidate:test:1",
                "source_document_id": "source-document:test",
                "question": "Questo documento conferma il claim?",
                "allowed_decisions": ["confirm", "reject_false_positive", "uncertain"],
                "priority": "high",
            },
        },
        {
            "record_id": "evidence-record:review-target-workflow",
            "record_kind": "review_queue_item",
            "subject_id": "",
            "source_document_id": "",
            "review_status": "pending",
            "payload_hash": "record-hash-review-target-workflow",
            "payload": {
                "@type": "MvpReviewQueueItem",
                "item_id": "review:item:workflow",
                "item_type": "mvp_warning_review",
                "subject_kind": "workflow",
                "decision_type": "workflow_triage",
                "question": "Warning tecnico da non usare come target storico.",
                "allowed_decisions": ["uncertain"],
            },
        },
        {
            "record_id": "evidence-record:historical-confirm",
            "record_kind": "historical_review_decision",
            "subject_id": "person:purocielo:test",
            "source_document_id": "source-document:test",
            "review_status": "pending",
            "payload_hash": "record-hash-historical-confirm",
            "payload": {
                "@type": "HistoricalReviewDecision",
                "decision_id": "historical-review-decision:confirm",
                "item_id": "review:item:1",
                "source_item_id": "candidate:test:1",
                "profile_id": "person:purocielo:test",
                "source_document_id": "source-document:test",
                "subject_kind": "claim",
                "selected_action": "confirm",
                "decision_status": "accepted",
                "reviewer": "storico-test",
                "reviewed_at": "2026-06-30",
                "candidate": {"field": "birth.date", "value": "1 gennaio 1920"},
            },
        },
        {
            "record_id": "evidence-record:historical-search",
            "record_kind": "historical_review_decision",
            "subject_id": "person:purocielo:test",
            "source_document_id": "source-document:test-2",
            "review_status": "pending",
            "payload_hash": "record-hash-historical-search",
            "payload": {
                "@type": "HistoricalReviewDecision",
                "decision_id": "historical-review-decision:search",
                "item_id": "review:item:2",
                "source_item_id": "candidate:test:2",
                "profile_id": "person:purocielo:test",
                "source_document_id": "source-document:test-2",
                "subject_kind": "document",
                "selected_action": "accept_for_search",
                "decision_status": "accepted",
                "reviewer": "storico-test",
                "reviewed_at": "2026-06-30",
                "candidate": {"field": "research.next_step", "value": "Cercare seconda fonte"},
            },
        },
    ]:
        record["import_batch_id"] = "evidence-import:run-forte-pipeline"
        record["source_run_id"] = "run-forte-pipeline"
        store.insert_evidence_record(record)
    return weak_run, strong_run


def write_sources_workspace(workspace: Path) -> None:
    intake = workspace / "documenti_da_processare"
    processed = workspace / "documenti_processati"
    (intake / "mvp_purocielo").mkdir(parents=True)
    (intake / "mvp_purocielo" / "registro_a.txt").write_text("Documento A", encoding="utf-8")
    (intake / "mvp_purocielo" / "registro_b.pdf").write_bytes(b"%PDF-1.4 fixture")
    (intake / "note_sciolte.txt").write_text("Nota sciolta", encoding="utf-8")
    (processed / "mvp_purocielo").mkdir(parents=True)
    (processed / "mvp_purocielo" / "registro_a.txt").write_text("Derivato", encoding="utf-8")


def write_online_sources_workspace(workspace: Path) -> None:
    registry = workspace / "ricerche" / "camalanca_fonti.yaml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        "\n".join(
            [
                "enabled_sources:",
                "- partigiani_italia",
                "- storia_memoria_bo",
                "sources:",
                "- id: partigiani_italia",
                "  name: Partigiani Italia fixture",
                "  kind: search_form_get_name",
                "- id: storia_memoria_bo",
                "  name: Storia e Memoria Bologna fixture",
                "  kind: search_url_only",
            ]
        ),
        encoding="utf-8",
    )
    write_json(
        workspace / "ricerche" / "person_profiles" / "purocielo.index.jsonld",
        {
            "profiles": [
                {"profile_id": "person:purocielo:test-1"},
                {"profile_id": "person:purocielo:test-2"},
            ]
        },
    )


def write_consolidate_workspace(workspace: Path) -> None:
    database_dir = workspace / "database"
    database_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteEvidenceStore(database_dir / "evidence.sqlite")
    store.init_schema()
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:run-con-ledger-pipeline",
            "source_run_id": "run-con-ledger-pipeline",
            "imported_at": "2026-06-30T10:00:00+00:00",
            "source_run_dir": str(workspace / "risultati" / "runs" / "run-con-ledger-pipeline"),
            "record_count": 3,
            "payload_hash": "batch-hash",
        }
    )
    for record in [
        {
            "record_id": "evidence-record:cli-link-1",
            "record_kind": "candidate_document_person_link",
            "subject_id": "person:purocielo:test",
            "source_document_id": "doc:test",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-link",
            "payload": {
                "@type": "CandidateDocumentPersonLink",
                "profile_id": "person:purocielo:test",
                "canonical_name": "Persona Test",
                "source_document_id": "doc:test",
                "matched_name": "Persona Test",
                "match_kind": "canonical_name",
            },
        },
        {
            "record_id": "evidence-record:cli-claim-1",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:test",
            "source_document_id": "doc:test",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-claim",
            "payload": {
                "@type": "CandidateEvidenceClaim",
                "profile_id": "person:purocielo:test",
                "source_document_id": "doc:test",
                "field": "birth.date",
                "value": "1 gennaio 1920",
            },
        },
        {
            "record_id": "evidence-record:cli-review-1",
            "record_kind": "review_queue_item",
            "subject_id": "",
            "source_document_id": "doc:test",
            "review_status": "pending",
            "payload_hash": "record-hash-review",
            "payload": {
                "@type": "MvpReviewQueueItem",
                "item_id": "review:item:test",
                "profile_id": "person:purocielo:test",
                "source_document_id": "doc:test",
                "question": "Confermare il collegamento documento-persona?",
            },
        },
    ]:
        record["import_batch_id"] = "evidence-import:run-con-ledger-pipeline"
        record["source_run_id"] = "run-con-ledger-pipeline"
        store.insert_evidence_record(record)
    runs_dir = workspace / "risultati" / "runs"
    run_with_ledger = runs_dir / "run-con-ledger-pipeline"
    run_without_ledger = runs_dir / "run-senza-ledger-pipeline"
    write_json(run_with_ledger / "mvp_consolidated_review_ledger.json", {"profiles": []})
    run_without_ledger.mkdir(parents=True, exist_ok=True)


class MemoriaCliTests(unittest.TestCase):
    def test_review_commands_discover_best_fixture_run(self) -> None:
        shell = powershell_exe()
        if shell is None:
            self.skipTest("PowerShell non disponibile")

        with workspace_temp_dir() as workspace:
            _, strong_run = write_review_workspace(workspace)

            discover_completed = run_memoria(shell, "review", "discover", "-WorkspaceRoot", str(workspace))
            review_status_completed = run_memoria(shell, "review", "status", "-WorkspaceRoot", str(workspace))
            alternatives_completed = run_memoria(shell, "review", "alternatives", "-WorkspaceRoot", str(workspace))
            alternatives_filtered_completed = run_memoria(
                shell,
                "review",
                "alternatives",
                "-ProfileId",
                "bagni-alfonso",
                "-WorkspaceRoot",
                str(workspace),
            )
            alternatives_created_session = (workspace / "database" / "memoria_review_session.active.json").exists()
            verified_dry_run_before_start_completed = run_memoria(
                shell,
                "review",
                "verified-facts",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            profile_patch_dry_run_before_start_completed = run_memoria(
                shell,
                "review",
                "profile-patch",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            store_dry_run_before_start_completed = run_memoria(
                shell,
                "review",
                "store",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            dataset_export_dry_run_before_start_completed = run_memoria(
                shell,
                "review",
                "dataset-export",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            verified_run_before_start_completed = run_memoria(
                shell,
                "review",
                "verified-facts",
                "run",
                "--preview",
                "-WorkspaceRoot",
                str(workspace),
            )
            start_completed = run_memoria(shell, "review", "start", "--auto", "-WorkspaceRoot", str(workspace))
            work_completed = run_memoria(shell, "review", "work", "-WorkspaceRoot", str(workspace))
            targets_dry_run_after_start_completed = run_memoria(
                shell,
                "review",
                "targets",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            targets_run_without_preview_completed = run_memoria_raw(
                shell,
                "review",
                "targets",
                "run",
                "-WorkspaceRoot",
                str(workspace),
            )
            verified_dry_run_after_start_completed = run_memoria(
                shell,
                "review",
                "verified-facts",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            verified_run_without_preview_completed = run_memoria_raw(
                shell,
                "review",
                "verified-facts",
                "run",
                "-WorkspaceRoot",
                str(workspace),
            )
            db_path = workspace / "database" / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            before_targets_records = store.count("evidence_records")
            before_targets_claims = store.count("evidence_claims")
            targets_run_completed = run_memoria(
                shell,
                "review",
                "targets",
                "run",
                "--preview",
                "-WorkspaceRoot",
                str(workspace),
            )
            after_targets_records = store.count("evidence_records")
            after_targets_claims = store.count("evidence_claims")
            store_dry_run_after_start_completed = run_memoria(
                shell,
                "review",
                "store",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            store_run_without_preview_completed = run_memoria_raw(
                shell,
                "review",
                "store",
                "run",
                "-WorkspaceRoot",
                str(workspace),
            )
            before_store_preview_records = store.count("evidence_records")
            before_store_preview_claims = store.count("evidence_claims")
            store_run_completed = run_memoria(
                shell,
                "review",
                "store",
                "run",
                "--preview",
                "-WorkspaceRoot",
                str(workspace),
            )
            after_store_preview_records = store.count("evidence_records")
            after_store_preview_claims = store.count("evidence_claims")
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")
            verified_run_completed = run_memoria(
                shell,
                "review",
                "verified-facts",
                "run",
                "--preview",
                "-WorkspaceRoot",
                str(workspace),
            )
            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")
            profile_patch_outputs_before = list((strong_run / "historian_review").glob("profile_patch.preview.*"))
            profile_patch_dry_run_after_start_completed = run_memoria(
                shell,
                "review",
                "profile-patch",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            profile_patch_run_without_preview_completed = run_memoria_raw(
                shell,
                "review",
                "profile-patch",
                "run",
                "-WorkspaceRoot",
                str(workspace),
            )
            before_profile_patch_records = store.count("evidence_records")
            before_profile_patch_claims = store.count("evidence_claims")
            profile_patch_run_completed = run_memoria(
                shell,
                "review",
                "profile-patch",
                "run",
                "--preview",
                "-WorkspaceRoot",
                str(workspace),
            )
            after_profile_patch_records = store.count("evidence_records")
            after_profile_patch_claims = store.count("evidence_claims")
            dataset_export_dry_run_after_start_completed = run_memoria(
                shell,
                "review",
                "dataset-export",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            dataset_export_run_without_preview_completed = run_memoria_raw(
                shell,
                "review",
                "dataset-export",
                "run",
                "-WorkspaceRoot",
                str(workspace),
            )
            dataset_export_show_missing_completed = run_memoria(
                shell,
                "review",
                "dataset-export",
                "show",
                "-WorkspaceRoot",
                str(workspace),
            )
            before_dataset_export_records = store.count("evidence_records")
            before_dataset_export_claims = store.count("evidence_claims")
            dataset_export_run_completed = run_memoria(
                shell,
                "review",
                "dataset-export",
                "run",
                "--preview",
                "-WorkspaceRoot",
                str(workspace),
            )
            dataset_export_show_completed = run_memoria(
                shell,
                "review",
                "dataset-export",
                "show",
                "-WorkspaceRoot",
                str(workspace),
            )
            after_dataset_export_records = store.count("evidence_records")
            after_dataset_export_claims = store.count("evidence_claims")
            profile_path = workspace / "ricerche" / "person_profiles" / "purocielo-test.jsonld"
            canonical_profile_before_sandbox = json.loads(profile_path.read_text(encoding="utf-8-sig"))
            profile_patch_json_path = strong_run / "historian_review" / "profile_patch.preview.json"
            multi_profile_patch_payload = json.loads(profile_patch_json_path.read_text(encoding="utf-8-sig"))
            multi_profile_patch_payload["profile_patches"].append(
                {
                    "@type": "ProfilePatch",
                    "profile_id": "person:purocielo:altro",
                    "operations": [{"op": "set", "path": "/birth/date", "value": "1921"}],
                }
            )
            multi_profile_patch_payload["patch_count"] = 2
            multi_profile_patch_payload["operation_count"] = 2
            write_json(profile_patch_json_path, multi_profile_patch_payload)
            profile_patch_apply_without_sandbox_completed = run_memoria_raw(
                shell,
                "review",
                "profile-patch",
                "apply",
                "-WorkspaceRoot",
                str(workspace),
            )
            profile_patch_apply_canonical_without_profile_completed = run_memoria_raw(
                shell,
                "review",
                "profile-patch",
                "apply",
                "--canonical",
                "-WorkspaceRoot",
                str(workspace),
            )
            profile_patch_apply_multi_without_profile_completed = run_memoria_raw(
                shell,
                "review",
                "profile-patch",
                "apply",
                "--sandbox",
                "-WorkspaceRoot",
                str(workspace),
            )
            before_sandbox_records = store.count("evidence_records")
            before_sandbox_claims = store.count("evidence_claims")
            profile_patch_apply_sandbox_completed = run_memoria(
                shell,
                "review",
                "profile-patch",
                "apply",
                "--sandbox",
                "-ProfileId",
                "person:purocielo:test",
                "-WorkspaceRoot",
                str(workspace),
            )
            after_sandbox_records = store.count("evidence_records")
            after_sandbox_claims = store.count("evidence_claims")
            canonical_profile_after_sandbox = json.loads(profile_path.read_text(encoding="utf-8-sig"))
            before_canonical_records = store.count("evidence_records")
            before_canonical_claims = store.count("evidence_claims")
            profile_patch_apply_canonical_completed = run_memoria(
                shell,
                "review",
                "profile-patch",
                "apply",
                "--canonical",
                "-ProfileId",
                "person:purocielo:test",
                "-WorkspaceRoot",
                str(workspace),
            )
            after_canonical_records = store.count("evidence_records")
            after_canonical_claims = store.count("evidence_claims")
            canonical_profile_after_apply = json.loads(profile_path.read_text(encoding="utf-8-sig"))
            before_review_command_records = store.count("evidence_records")
            before_review_command_claims = store.count("evidence_claims")
            accept_completed = run_memoria(shell, "review", "accept", "1", "-WorkspaceRoot", str(workspace))
            reject_completed = run_memoria(shell, "review", "reject", "2", "-WorkspaceRoot", str(workspace))
            uncertain_completed = run_memoria(shell, "review", "uncertain", "2", "-WorkspaceRoot", str(workspace))
            after_review_command_records = store.count("evidence_records")
            after_review_command_claims = store.count("evidence_claims")
            refresh_completed = run_memoria(shell, "review", "refresh", "-WorkspaceRoot", str(workspace))
            dashboard_completed = run_memoria(shell, "review", "dashboard", "-WorkspaceRoot", str(workspace))
            dashboard_show_completed = run_memoria(shell, "review", "dashboard", "show", "-WorkspaceRoot", str(workspace))
            status_completed = run_memoria(shell, "status", "-WorkspaceRoot", str(workspace))
            session_path = workspace / "database" / "memoria_review_session.active.json"
            session_exists = session_path.exists()
            session_payload = json.loads(session_path.read_text(encoding="utf-8-sig"))
            dashboard_json_path = strong_run / "historian_review" / "review_dashboard.json"
            dashboard_md_path = strong_run / "historian_review" / "review_dashboard.md"
            dashboard_exists = dashboard_json_path.exists() and dashboard_md_path.exists()
            dashboard_payload = json.loads(dashboard_json_path.read_text(encoding="utf-8-sig"))
            dashboard_markdown = dashboard_md_path.read_text(encoding="utf-8")
            targets_json_path = strong_run / "historian_review" / "historical_review_targets.store_first.json"
            targets_md_path = strong_run / "historian_review" / "historical_review_targets.store_first.md"
            targets_exists = targets_json_path.exists() and targets_md_path.exists()
            targets_payload = json.loads(targets_json_path.read_text(encoding="utf-8-sig"))
            targets_markdown = targets_md_path.read_text(encoding="utf-8")
            review_register_json_path = strong_run / "historian_review" / "review_decision_conflict_register.preview.json"
            review_register_md_path = strong_run / "historian_review" / "review_decision_conflict_register.preview.md"
            review_store_json_path = strong_run / "historian_review" / "review_store.preview.json"
            review_store_md_path = strong_run / "historian_review" / "review_store.preview.md"
            review_store_exists = (
                review_register_json_path.exists()
                and review_register_md_path.exists()
                and review_store_json_path.exists()
                and review_store_md_path.exists()
            )
            review_store_payload = json.loads(review_store_json_path.read_text(encoding="utf-8-sig"))
            review_store_markdown = review_store_md_path.read_text(encoding="utf-8")
            verified_facts_path = strong_run / "historian_review" / "verified_facts.preview.json"
            verified_facts_exists = verified_facts_path.exists()
            verified_facts_payload = json.loads(verified_facts_path.read_text(encoding="utf-8-sig"))
            profile_patch_md_path = strong_run / "historian_review" / "profile_patch.preview.md"
            profile_patch_exists = profile_patch_json_path.exists() and profile_patch_md_path.exists()
            profile_patch_payload = json.loads(profile_patch_json_path.read_text(encoding="utf-8-sig"))
            profile_patch_markdown = profile_patch_md_path.read_text(encoding="utf-8")
            dataset_export_json_path = strong_run / "historian_review" / "dataset_export.preview.json"
            dataset_export_md_path = strong_run / "historian_review" / "dataset_export.preview.md"
            dataset_export_exists = dataset_export_json_path.exists() and dataset_export_md_path.exists()
            dataset_export_payload = json.loads(dataset_export_json_path.read_text(encoding="utf-8-sig"))
            dataset_export_markdown = dataset_export_md_path.read_text(encoding="utf-8")
            sandbox_dir = strong_run / "historian_review" / "profile_patch_sandbox"
            sandbox_profile_path = sandbox_dir / "person-purocielo-test.sandbox.profile.jsonld"
            sandbox_promotion_path = sandbox_dir / "person-purocielo-test.sandbox.promotion.json"
            sandbox_audit_path = sandbox_dir / "person-purocielo-test.sandbox.audit.json"
            sandbox_profile_exists = sandbox_profile_path.exists()
            sandbox_payload = json.loads(sandbox_profile_path.read_text(encoding="utf-8-sig"))
            sandbox_promotion = json.loads(sandbox_promotion_path.read_text(encoding="utf-8-sig"))
            sandbox_audit = json.loads(sandbox_audit_path.read_text(encoding="utf-8-sig"))
            canonical_apply_dir = strong_run / "historian_review" / "profile_patch_apply"
            canonical_promotion_path = canonical_apply_dir / "person-purocielo-test.apply.promotion.json"
            canonical_audit_path = canonical_apply_dir / "person-purocielo-test.apply.audit.json"
            canonical_backup_files = list((canonical_apply_dir / "backups").glob("*.backup.jsonld"))
            canonical_promotion = json.loads(canonical_promotion_path.read_text(encoding="utf-8-sig"))
            canonical_audit = json.loads(canonical_audit_path.read_text(encoding="utf-8-sig"))
            compiled_decisions_path = strong_run / "historian_review" / "review_decisions.compilato.json"
            compiled_decisions = json.loads(compiled_decisions_path.read_text(encoding="utf-8-sig"))
            decisions_summary_path = strong_run / "historian_review" / "review_decisions_summary.json"
            decisions_summary = json.loads(decisions_summary_path.read_text(encoding="utf-8-sig"))

        for completed in (discover_completed, review_status_completed):
            self.assertIn("Me.Mo.Ria review discovery", completed.stdout)
            self.assertIn("[1] run-forte-pipeline", completed.stdout)
            self.assertIn("Decisioni storiche sostanziali: 1", completed.stdout)
            self.assertIn("preview-only/read-only", completed.stdout)
        self.assertIn("Me.Mo.Ria review alternatives", alternatives_completed.stdout)
        self.assertIn("Run attiva: non presente", alternatives_completed.stdout)
        self.assertIn("run-forte-pipeline", alternatives_completed.stdout)
        self.assertIn("Persona Test", alternatives_completed.stdout)
        self.assertIn("person:purocielo:test", alternatives_completed.stdout)
        self.assertIn("run-alternativa-pipeline", alternatives_completed.stdout)
        self.assertIn("Bagni Alfonso", alternatives_completed.stdout)
        self.assertIn("Item revisionabili: 1", alternatives_completed.stdout)
        self.assertIn("non cambia run attiva", alternatives_completed.stdout)
        self.assertIn("Filtro ProfileId: bagni-alfonso", alternatives_filtered_completed.stdout)
        self.assertIn("Bagni Alfonso", alternatives_filtered_completed.stdout)
        self.assertNotIn("Persona Test", alternatives_filtered_completed.stdout)
        self.assertFalse(alternatives_created_session)
        self.assertIn("Run attiva: run-forte-pipeline", start_completed.stdout)
        self.assertIn("Worklist item: 2", start_completed.stdout)
        self.assertIn("review work", start_completed.stdout)
        self.assertIn("Nessuna sessione review attiva.", verified_dry_run_before_start_completed.stdout)
        self.assertIn("review start --auto", verified_dry_run_before_start_completed.stdout)
        self.assertIn("Nessuna sessione review attiva.", profile_patch_dry_run_before_start_completed.stdout)
        self.assertIn("review start --auto", profile_patch_dry_run_before_start_completed.stdout)
        self.assertIn("Nessuna sessione review attiva.", store_dry_run_before_start_completed.stdout)
        self.assertIn("review start --auto", store_dry_run_before_start_completed.stdout)
        self.assertIn("Nessuna sessione review attiva.", dataset_export_dry_run_before_start_completed.stdout)
        self.assertIn("review start --auto", dataset_export_dry_run_before_start_completed.stdout)
        self.assertIn("Nessuna sessione review attiva.", verified_run_before_start_completed.stdout)
        self.assertIn("review start --auto", verified_run_before_start_completed.stdout)
        self.assertIn("Me.Mo.Ria review work", work_completed.stdout)
        self.assertIn("[1] Persona Test | claim | pending", work_completed.stdout)
        self.assertIn("review:item:1", work_completed.stdout)
        self.assertIn("File sorgente: documenti_da_processare/purocielo/test.pdf", work_completed.stdout)
        self.assertIn("Metadata: documenti_processati/purocielo/test.metadata.json", work_completed.stdout)
        self.assertIn("Questo documento conferma il claim?", work_completed.stdout)
        self.assertIn("Me.Mo.Ria review targets dry-run", targets_dry_run_after_start_completed.stdout)
        self.assertIn("build_mvp_historical_review_targets.ps1", targets_dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceDatabasePath", targets_dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceSourceRunId", targets_dry_run_after_start_completed.stdout)
        self.assertIn("Modalita sorgente proposta: evidence_store", targets_dry_run_after_start_completed.stdout)
        self.assertIn("historical_review_targets.store_first.json", targets_dry_run_after_start_completed.stdout)
        self.assertNotEqual(targets_run_without_preview_completed.returncode, 0)
        self.assertIn("review targets run usare --preview", targets_run_without_preview_completed.stderr)
        self.assertIn("Me.Mo.Ria review targets run", targets_run_completed.stdout)
        self.assertIn("Sorgente: evidence_store", targets_run_completed.stdout)
        self.assertIn("Target storici preview generati.", targets_run_completed.stdout)
        self.assertIn("non crea decisioni storiche", targets_run_completed.stdout)
        self.assertIn("Me.Mo.Ria review store dry-run", store_dry_run_after_start_completed.stdout)
        self.assertIn("build_review_decision_conflict_register_preview.ps1", store_dry_run_after_start_completed.stdout)
        self.assertIn("build_review_store_preview.ps1", store_dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceDatabasePath", store_dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceSourceRunId", store_dry_run_after_start_completed.stdout)
        self.assertIn("review_decision_conflict_register.preview.json", store_dry_run_after_start_completed.stdout)
        self.assertIn("review_store.preview.json", store_dry_run_after_start_completed.stdout)
        self.assertNotEqual(store_run_without_preview_completed.returncode, 0)
        self.assertIn("review store run usare --preview", store_run_without_preview_completed.stderr)
        self.assertIn("Me.Mo.Ria review store run", store_run_completed.stdout)
        self.assertIn("Review store preview generata.", store_run_completed.stdout)
        self.assertIn("non crea decisioni canoniche", store_run_completed.stdout)
        self.assertIn("Me.Mo.Ria review verified-facts dry-run", verified_dry_run_after_start_completed.stdout)
        self.assertIn("build_verified_facts_preview.ps1", verified_dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceDatabasePath", verified_dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceSourceRunId", verified_dry_run_after_start_completed.stdout)
        self.assertIn("run-forte-pipeline", verified_dry_run_after_start_completed.stdout)
        self.assertIn("verified_facts.preview.json", verified_dry_run_after_start_completed.stdout)
        self.assertNotEqual(verified_run_without_preview_completed.returncode, 0)
        self.assertIn("review verified-facts run usare --preview", verified_run_without_preview_completed.stderr)
        self.assertIn("Me.Mo.Ria review verified-facts run", verified_run_completed.stdout)
        self.assertIn("Verified facts preview generata.", verified_run_completed.stdout)
        self.assertIn("non crea verified_facts canonici", verified_run_completed.stdout)
        self.assertEqual(profile_patch_outputs_before, [])
        self.assertIn("Me.Mo.Ria review profile-patch dry-run", profile_patch_dry_run_after_start_completed.stdout)
        self.assertIn("build_verified_facts_profile_patch_preview.ps1", profile_patch_dry_run_after_start_completed.stdout)
        self.assertIn("-VerifiedFactsPreviewJson", profile_patch_dry_run_after_start_completed.stdout)
        self.assertIn("verified_facts.preview.json", profile_patch_dry_run_after_start_completed.stdout)
        self.assertIn("profile_patch.preview.json", profile_patch_dry_run_after_start_completed.stdout)
        self.assertNotEqual(profile_patch_run_without_preview_completed.returncode, 0)
        self.assertIn("review profile-patch run usare --preview", profile_patch_run_without_preview_completed.stderr)
        self.assertIn("Me.Mo.Ria review profile-patch run", profile_patch_run_completed.stdout)
        self.assertIn("ProfilePatch preview generata.", profile_patch_run_completed.stdout)
        self.assertIn("non applica ProfilePatch", profile_patch_run_completed.stdout)
        self.assertIn("Me.Mo.Ria review dataset-export dry-run", dataset_export_dry_run_after_start_completed.stdout)
        self.assertIn("build_dataset_export_preview.ps1", dataset_export_dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceDatabasePath", dataset_export_dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceSourceRunId", dataset_export_dry_run_after_start_completed.stdout)
        self.assertIn("verified_facts.preview.json", dataset_export_dry_run_after_start_completed.stdout)
        self.assertIn("profile_patch.preview.json", dataset_export_dry_run_after_start_completed.stdout)
        self.assertIn("dataset_export.preview.json", dataset_export_dry_run_after_start_completed.stdout)
        self.assertNotEqual(dataset_export_run_without_preview_completed.returncode, 0)
        self.assertIn("review dataset-export run usare --preview", dataset_export_run_without_preview_completed.stderr)
        self.assertIn("Me.Mo.Ria review dataset-export show", dataset_export_show_missing_completed.stdout)
        self.assertIn("dataset_export.preview.md", dataset_export_show_missing_completed.stdout)
        self.assertIn("Stato: non disponibile", dataset_export_show_missing_completed.stdout)
        self.assertIn("review dataset-export run --preview", dataset_export_show_missing_completed.stdout)
        self.assertIn("Me.Mo.Ria review dataset-export run", dataset_export_run_completed.stdout)
        self.assertIn("Dataset export preview generata.", dataset_export_run_completed.stdout)
        self.assertIn("non crea dataset canonici", dataset_export_run_completed.stdout)
        self.assertIn("Me.Mo.Ria review dataset-export show", dataset_export_show_completed.stdout)
        self.assertIn("dataset_export.preview.md", dataset_export_show_completed.stdout)
        self.assertIn("## Dataset export preview", dataset_export_show_completed.stdout)
        self.assertIn("Non e' un dataset canonico", dataset_export_show_completed.stdout)
        self.assertIn("comando read-only", dataset_export_show_completed.stdout)
        self.assertNotEqual(profile_patch_apply_without_sandbox_completed.returncode, 0)
        self.assertIn("review profile-patch apply usare --sandbox oppure --canonical", profile_patch_apply_without_sandbox_completed.stderr)
        self.assertNotEqual(profile_patch_apply_canonical_without_profile_completed.returncode, 0)
        self.assertIn("apply --canonical specificare -ProfileId", profile_patch_apply_canonical_without_profile_completed.stderr)
        self.assertNotEqual(profile_patch_apply_multi_without_profile_completed.returncode, 0)
        self.assertIn("ProfilePatch preview contiene piu' profili", profile_patch_apply_multi_without_profile_completed.stderr)
        self.assertIn("Rilanciare con -ProfileId", profile_patch_apply_multi_without_profile_completed.stderr)
        self.assertIn("person:purocielo:test", profile_patch_apply_multi_without_profile_completed.stderr)
        self.assertIn("person:purocielo:altro", profile_patch_apply_multi_without_profile_completed.stderr)
        self.assertIn("Me.Mo.Ria review profile-patch apply", profile_patch_apply_sandbox_completed.stdout)
        self.assertIn("Modalita: sandbox", profile_patch_apply_sandbox_completed.stdout)
        self.assertIn("Profile ID: person:purocielo:test", profile_patch_apply_sandbox_completed.stdout)
        self.assertIn("ProfilePatch applicata in sandbox.", profile_patch_apply_sandbox_completed.stdout)
        self.assertIn("profilo canonico non modificato", profile_patch_apply_sandbox_completed.stdout)
        self.assertIn("Me.Mo.Ria review profile-patch apply", profile_patch_apply_canonical_completed.stdout)
        self.assertIn("Modalita: canonical", profile_patch_apply_canonical_completed.stdout)
        self.assertIn("Profile ID: person:purocielo:test", profile_patch_apply_canonical_completed.stdout)
        self.assertIn("ProfilePatch applicata al profilo canonico.", profile_patch_apply_canonical_completed.stdout)
        self.assertIn("profile_patch_apply", profile_patch_apply_canonical_completed.stdout)
        self.assertIn("review accept 1", work_completed.stdout)
        self.assertIn("Me.Mo.Ria review accept", accept_completed.stdout)
        self.assertIn("Azione selezionata: confirm", accept_completed.stdout)
        self.assertIn("review_decisions.compilato.json", accept_completed.stdout)
        self.assertIn("non crea verified_facts", accept_completed.stdout)
        self.assertIn("Me.Mo.Ria review reject", reject_completed.stdout)
        self.assertIn("Azione selezionata: reject_false_positive", reject_completed.stdout)
        self.assertIn("Me.Mo.Ria review uncertain", uncertain_completed.stdout)
        self.assertIn("Azione selezionata: uncertain", uncertain_completed.stdout)
        self.assertIn("non modifica profili JSON-LD", uncertain_completed.stdout)
        self.assertIn("Me.Mo.Ria review refresh", refresh_completed.stdout)
        self.assertIn("Dashboard aggiornata", refresh_completed.stdout)
        self.assertIn("review_dashboard.md", refresh_completed.stdout)
        self.assertIn("Me.Mo.Ria review dashboard", dashboard_completed.stdout)
        self.assertIn("Dashboard disponibile", dashboard_completed.stdout)
        self.assertIn("review_dashboard.json", dashboard_completed.stdout)
        self.assertIn("Me.Mo.Ria review dashboard show", dashboard_show_completed.stdout)
        self.assertIn("review_dashboard.md", dashboard_show_completed.stdout)
        self.assertIn("verified_facts.preview.md", dashboard_show_completed.stdout)
        self.assertIn("profile_patch.preview.md", dashboard_show_completed.stdout)
        self.assertIn("## Verified facts preview", dashboard_show_completed.stdout)
        self.assertIn("Fatti preview: `1`", dashboard_show_completed.stdout)
        self.assertIn("## ProfilePatch preview", dashboard_show_completed.stdout)
        self.assertIn("Non applica ProfilePatch", dashboard_show_completed.stdout)
        self.assertIn("comando read-only", dashboard_show_completed.stdout)
        self.assertIn("## Verified facts preview", dashboard_markdown)
        self.assertIn("Fatti preview: `1`", dashboard_markdown)
        self.assertIn("## ProfilePatch preview", dashboard_markdown)
        self.assertIn("ProfilePatch: `2`", dashboard_markdown)
        self.assertIn("## ProfilePatch sandbox", dashboard_markdown)
        self.assertIn("Profili derivati: `1`", dashboard_markdown)
        self.assertIn("Me.Mo.Ria review status", status_completed.stdout)
        self.assertIn("Run attiva: run-forte-pipeline", status_completed.stdout)
        self.assertIn("Decisioni sessione: 2/2", status_completed.stdout)
        self.assertIn("Pendenti: 0", status_completed.stdout)
        self.assertIn("Ultima decisione: [2] review:item:2 -> uncertain", status_completed.stdout)
        self.assertIn("Dashboard: disponibile", status_completed.stdout)
        self.assertIn("review_dashboard.json", status_completed.stdout)
        self.assertIn("review_dashboard.md", status_completed.stdout)
        self.assertTrue(session_exists)
        self.assertTrue(session_payload["preview_only"])
        self.assertEqual(session_payload["selected_run_id"], "run-forte-pipeline")
        self.assertEqual(session_payload["worklist_item_count"], 2)
        self.assertEqual(session_payload["worklist"][0]["raw_file"], "documenti_da_processare/purocielo/test.pdf")
        self.assertEqual(session_payload["worklist"][0]["metadata_file"], "documenti_processati/purocielo/test.metadata.json")
        self.assertEqual(session_payload["last_decision_item_id"], "review:item:2")
        self.assertEqual(session_payload["last_selected_action"], "uncertain")
        self.assertTrue(dashboard_exists)
        accepted_decision = next(item for item in compiled_decisions["decisions"] if item["item_id"] == "review:item:1")
        uncertain_decision = next(item for item in compiled_decisions["decisions"] if item["item_id"] == "review:item:2")
        self.assertEqual(accepted_decision["selected_action"], "confirm")
        self.assertEqual(accepted_decision["reviewer"], "memoria-cli")
        self.assertEqual(uncertain_decision["selected_action"], "uncertain")
        self.assertEqual(uncertain_decision["reviewer"], "memoria-cli")
        self.assertEqual(decisions_summary["accepted_count"], 2)
        self.assertEqual(decisions_summary["pending_count"], 0)
        self.assertEqual(decisions_summary["validation_error_count"], 0)
        self.assertEqual(decisions_summary["counts_by_action"]["confirm"], 1)
        self.assertEqual(decisions_summary["counts_by_action"]["uncertain"], 1)
        self.assertEqual(dashboard_payload["@type"], "MvpReviewDashboard")
        self.assertTrue(dashboard_payload["output_policy"]["preview_only"])
        self.assertFalse(dashboard_payload["output_policy"]["creates_validated_facts"])
        self.assertIn("verified_facts_preview", dashboard_payload)
        self.assertIn("profile_patch_preview", dashboard_payload)
        self.assertIn("profile_patch_sandbox", dashboard_payload)
        self.assertEqual(dashboard_payload["profile_patch_preview"]["patch_count"], 2)
        self.assertEqual(dashboard_payload["profile_patch_sandbox"]["sandbox_profile_count"], 1)
        self.assertIn("Review dashboard MVP", dashboard_markdown)
        self.assertIn("Persona Test", dashboard_markdown)
        self.assertTrue(targets_exists)
        self.assertEqual(targets_payload["source_mode"], "evidence_store")
        self.assertEqual(targets_payload["source_run_ids"], ["run-forte-pipeline"])
        self.assertEqual(targets_payload["target_count"], 1)
        self.assertEqual(targets_payload["targets"][0]["source_record_id"], "evidence-record:review-target-1")
        self.assertEqual(targets_payload["targets"][0]["current_selected_action"], "confirm")
        self.assertIn("Target storici revisionabili MVP", targets_markdown)
        self.assertIn("Modalita' sorgente: `evidence_store`", targets_markdown)
        self.assertIn("Decisione corrente: `confirm` / `accepted`", targets_markdown)
        self.assertEqual(before_targets_records, after_targets_records)
        self.assertEqual(before_targets_claims, after_targets_claims)
        self.assertTrue(review_store_exists)
        self.assertTrue(review_store_payload["preview_only"])
        self.assertEqual(review_store_payload["source_run_ids"], ["run-forte-pipeline"])
        self.assertGreaterEqual(len(review_store_payload["review_decisions"]), 2)
        self.assertIn("Review store preview", review_store_markdown)
        self.assertEqual(before_store_preview_records, after_store_preview_records)
        self.assertEqual(before_store_preview_claims, after_store_preview_claims)
        self.assertTrue(verified_facts_exists)
        self.assertEqual(verified_facts_payload["fact_count"], 1)
        self.assertEqual(verified_facts_payload["excluded_decision_count"], 1)
        self.assertEqual(verified_facts_payload["facts"][0]["field"], "birth.date")
        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        self.assertTrue(profile_patch_exists)
        self.assertEqual(profile_patch_payload["@type"], "ProfilePatchPreviewBatch")
        self.assertTrue(profile_patch_payload["preview_only"])
        self.assertEqual(profile_patch_payload["patch_count"], 2)
        self.assertEqual(profile_patch_payload["operation_count"], 2)
        self.assertEqual(profile_patch_payload["profile_patches"][0]["profile_id"], "person:purocielo:test")
        self.assertIn("Non applica ProfilePatch", profile_patch_markdown)
        self.assertEqual(before_profile_patch_records, after_profile_patch_records)
        self.assertEqual(before_profile_patch_claims, after_profile_patch_claims)
        self.assertTrue(dataset_export_exists)
        self.assertTrue(dataset_export_payload["preview_only"])
        self.assertEqual(dataset_export_payload["source_run_ids"], ["run-forte-pipeline"])
        self.assertEqual(dataset_export_payload["verified_facts_preview"]["fact_count"], 1)
        self.assertEqual(dataset_export_payload["profile_patch_preview"]["patch_count"], 1)
        self.assertIn("Dataset export preview", dataset_export_markdown)
        self.assertIn("Non e' un dataset canonico", dataset_export_markdown)
        self.assertEqual(before_dataset_export_records, after_dataset_export_records)
        self.assertEqual(before_dataset_export_claims, after_dataset_export_claims)
        self.assertTrue(sandbox_profile_exists)
        self.assertEqual(canonical_profile_before_sandbox, canonical_profile_after_sandbox)
        self.assertEqual(sandbox_payload["birth"]["date"], "1 gennaio 1920")
        self.assertEqual(sandbox_promotion["status"], "sandbox")
        self.assertTrue(sandbox_promotion["sandbox"])
        self.assertFalse(sandbox_promotion["writes_canonical_profile"])
        self.assertFalse(sandbox_audit["dry_run"])
        self.assertTrue(sandbox_audit["changed"])
        self.assertEqual(before_sandbox_records, after_sandbox_records)
        self.assertEqual(before_sandbox_claims, after_sandbox_claims)
        self.assertEqual(canonical_profile_after_apply["birth"]["date"], "1 gennaio 1920")
        self.assertEqual(canonical_promotion["status"], "applied")
        self.assertFalse(canonical_promotion["dry_run"])
        self.assertFalse(canonical_promotion["sandbox"])
        self.assertTrue(canonical_promotion["writes_canonical_profile"])
        self.assertFalse(canonical_audit["dry_run"])
        self.assertTrue(canonical_audit["changed"])
        self.assertEqual(len(canonical_backup_files), 1)
        self.assertEqual(before_canonical_records, after_canonical_records)
        self.assertEqual(before_canonical_claims, after_canonical_claims)
        self.assertEqual(before_review_command_records, after_review_command_records)
        self.assertEqual(before_review_command_claims, after_review_command_claims)

    def test_memoria_script_declares_preview_only_guards(self) -> None:
        text = (ROOT_DIR / "scripts" / "memoria.ps1").read_text(encoding="utf-8")

        self.assertIn("preview-only", text)
        self.assertIn("non crea verified_facts", text)
        self.assertIn("non modifica profili JSON-LD", text)
        self.assertIn('$Root = "P:\\Comune\\Me.Mo.Ri.a"', text)
        self.assertIn("sources online discover", text)
        self.assertIn("sources offline discover", text)
        self.assertIn("consolidate discover", text)
        self.assertIn("consolidate profile-status", text)
        self.assertIn("review alternatives", text)
        self.assertIn("review work", text)
        self.assertIn("review accept", text)
        self.assertIn("review reject", text)
        self.assertIn("review uncertain", text)
        self.assertIn("review refresh", text)
        self.assertIn("review dashboard", text)
        self.assertIn("review dashboard show", text)
        self.assertIn("review targets", text)
        self.assertIn("review store", text)
        self.assertIn("review dataset-export", text)
        self.assertIn("review dataset-export show", text)
        self.assertIn("review verified-facts", text)
        self.assertIn("review profile-patch", text)

    def test_sources_offline_discovery_is_read_only(self) -> None:
        shell = powershell_exe()
        if shell is None:
            self.skipTest("PowerShell non disponibile")

        with workspace_temp_dir() as workspace:
            write_sources_workspace(workspace)

            discover_completed = run_memoria(shell, "sources", "offline", "discover", "-WorkspaceRoot", str(workspace))
            status_completed = run_memoria(shell, "sources", "offline", "status", "-WorkspaceRoot", str(workspace))
            start_completed = run_memoria(shell, "sources", "offline", "start", "--auto", "-WorkspaceRoot", str(workspace))
            runs_dir = workspace / "risultati" / "runs"
            database_dir = workspace / "database"

        for completed in (discover_completed, status_completed):
            self.assertIn("Me.Mo.Ria sources offline discovery", completed.stdout)
            self.assertIn("Modalita: preview-only/read-only", completed.stdout)
            self.assertIn("Cartelle candidate: 1", completed.stdout)
            self.assertIn("File candidati: 3", completed.stdout)
            self.assertIn("File processati: 1", completed.stdout)
            self.assertIn("mvp_purocielo", completed.stdout)
            self.assertIn("note_sciolte.txt", completed.stdout)
            self.assertIn("non crea run", completed.stdout)
        self.assertIn("Me.Mo.Ria sources offline start", start_completed.stdout)
        self.assertIn("non avvia OCR, pipeline o import", start_completed.stdout)
        self.assertFalse(runs_dir.exists())
        self.assertFalse(database_dir.exists())

    def test_sources_online_discovery_is_read_only(self) -> None:
        shell = powershell_exe()
        if shell is None:
            self.skipTest("PowerShell non disponibile")

        with workspace_temp_dir() as workspace:
            write_online_sources_workspace(workspace)

            discover_completed = run_memoria(shell, "sources", "online", "discover", "-WorkspaceRoot", str(workspace))
            status_completed = run_memoria(shell, "sources", "online", "status", "-WorkspaceRoot", str(workspace))
            start_completed = run_memoria(shell, "sources", "online", "start", "--auto", "-WorkspaceRoot", str(workspace))
            session_path = workspace / "database" / "memoria_sources_online_session.active.json"
            start_without_subject_created_session = session_path.exists()
            profile_subject_completed = run_memoria(
                shell,
                "sources",
                "online",
                "discover",
                "-ProfileId",
                "person:purocielo:test-1",
                "-WorkspaceRoot",
                str(workspace),
            )
            place_subject_completed = run_memoria(
                shell,
                "sources",
                "online",
                "discover",
                "-SubjectKind",
                "place",
                "-SubjectId",
                "place:test:monte-battaglia",
                "-SubjectLabel",
                "Monte Battaglia",
                "-WorkspaceRoot",
                str(workspace),
            )
            event_subject_completed = run_memoria(
                shell,
                "sources",
                "online",
                "start",
                "--auto",
                "-SubjectKind",
                "event",
                "-SubjectId",
                "event:test:liberazione",
                "-SubjectLabel",
                "Liberazione fixture",
                "-WorkspaceRoot",
                str(workspace),
            )
            status_after_session_completed = run_memoria(
                shell,
                "sources",
                "online",
                "status",
                "-WorkspaceRoot",
                str(workspace),
            )
            invalid_subject_completed = run_memoria_raw(
                shell,
                "sources",
                "online",
                "discover",
                "-SubjectKind",
                "formation",
                "-SubjectId",
                "formation:test",
                "-WorkspaceRoot",
                str(workspace),
            )
            runs_dir = workspace / "risultati" / "runs"
            database_dir = workspace / "database"
            evidence_db = database_dir / "evidence.sqlite"
            sources_online_intake_dir = workspace / "documenti_da_processare" / "sources_online"
            session_payload = json.loads(session_path.read_text(encoding="utf-8"))
            runs_dir_exists = runs_dir.exists()
            database_dir_exists = database_dir.exists()
            evidence_db_exists = evidence_db.exists()
            sources_online_intake_dir_exists = sources_online_intake_dir.exists()

        for completed in (discover_completed, status_completed):
            self.assertIn("Me.Mo.Ria sources online discovery", completed.stdout)
            self.assertIn("Modalita: preview-only/read-only", completed.stdout)
            self.assertIn("Registry fonti:", completed.stdout)
            self.assertIn("Fonti abilitate:", completed.stdout)
            self.assertIn("Definizioni fonte:", completed.stdout)
            self.assertIn("Profili candidati: 2", completed.stdout)
            self.assertIn("partigiani_italia", completed.stdout)
            self.assertIn("storia_memoria_bo", completed.stdout)
            self.assertIn("non crea run", completed.stdout)
        self.assertIn("Soggetto storico richiesto:", profile_subject_completed.stdout)
        self.assertIn("Tipo: person", profile_subject_completed.stdout)
        self.assertIn("ID: person:purocielo:test-1", profile_subject_completed.stdout)
        self.assertIn("fonte/evidenza candidata", profile_subject_completed.stdout)
        self.assertIn("Soggetto storico richiesto:", place_subject_completed.stdout)
        self.assertIn("Tipo: place", place_subject_completed.stdout)
        self.assertIn("ID: place:test:monte-battaglia", place_subject_completed.stdout)
        self.assertIn("Etichetta: Monte Battaglia", place_subject_completed.stdout)
        self.assertIn("Intake proposto:", place_subject_completed.stdout)
        self.assertIn("Query seed candidata: Monte Battaglia", place_subject_completed.stdout)
        self.assertIn("Me.Mo.Ria sources online start", event_subject_completed.stdout)
        self.assertIn("Tipo: event", event_subject_completed.stdout)
        self.assertIn("ID: event:test:liberazione", event_subject_completed.stdout)
        self.assertIn("Liberazione fixture", event_subject_completed.stdout)
        self.assertIn("Sessione preview:", event_subject_completed.stdout)
        self.assertIn("Sessione sources online attiva:", status_after_session_completed.stdout)
        self.assertIn("Stato: presente", status_after_session_completed.stdout)
        self.assertIn("event event:test:liberazione", status_after_session_completed.stdout)
        self.assertTrue(session_payload["preview_only"])
        self.assertEqual(session_payload["@type"], "MemoriaSourcesOnlineSession")
        self.assertEqual(session_payload["subject"]["kind"], "event")
        self.assertEqual(session_payload["subject"]["id"], "event:test:liberazione")
        self.assertEqual(session_payload["candidate_query"]["seed"], "Liberazione fixture")
        self.assertEqual(session_payload["candidate_record_preview"]["review_status"], "unreviewed")
        self.assertIn("sources_online", session_payload["proposed_intake_path"])
        candidate_source_ids = [source["source_id"] for source in session_payload["candidate_sources"]]
        self.assertIn("partigiani_italia", candidate_source_ids)
        self.assertIn("storia_memoria_bo", candidate_source_ids)
        self.assertFalse(start_without_subject_created_session)
        self.assertNotEqual(0, invalid_subject_completed.returncode)
        self.assertIn("SubjectKind non supportato", invalid_subject_completed.stderr)
        self.assertIn("Me.Mo.Ria sources online start", start_completed.stdout)
        self.assertIn("non avvia rete, browser, login, pipeline o import", start_completed.stdout)
        self.assertFalse(runs_dir_exists)
        self.assertTrue(database_dir_exists)
        self.assertFalse(evidence_db_exists)
        self.assertFalse(sources_online_intake_dir_exists)

    def test_consolidate_discovery_is_read_only(self) -> None:
        shell = powershell_exe()
        if shell is None:
            self.skipTest("PowerShell non disponibile")

        with workspace_temp_dir() as workspace:
            write_consolidate_workspace(workspace)

            discover_completed = run_memoria(shell, "consolidate", "discover", "-WorkspaceRoot", str(workspace))
            dry_run_before_start_completed = run_memoria(shell, "consolidate", "dry-run", "-WorkspaceRoot", str(workspace))
            run_before_start_completed = run_memoria(shell, "consolidate", "run", "--preview", "-WorkspaceRoot", str(workspace))
            profile_status_before_start_completed = run_memoria(
                shell,
                "consolidate",
                "profile-status",
                "dry-run",
                "-ProfileId",
                "person:purocielo:test",
                "-WorkspaceRoot",
                str(workspace),
            )
            status_before_start_completed = run_memoria(shell, "consolidate", "status", "-WorkspaceRoot", str(workspace))
            session_path = workspace / "database" / "memoria_consolidate_session.active.json"
            session_exists_before_start = session_path.exists()
            run_without_preview_completed = run_memoria_raw(shell, "consolidate", "run", "-WorkspaceRoot", str(workspace))
            start_completed = run_memoria(shell, "consolidate", "start", "--auto", "-WorkspaceRoot", str(workspace))
            status_after_start_completed = run_memoria(shell, "consolidate", "status", "-WorkspaceRoot", str(workspace))
            dry_run_after_start_completed = run_memoria(shell, "consolidate", "dry-run", "-WorkspaceRoot", str(workspace))
            profile_status_without_profile_completed = run_memoria_raw(
                shell,
                "consolidate",
                "profile-status",
                "dry-run",
                "-WorkspaceRoot",
                str(workspace),
            )
            profile_status_run_without_preview_completed = run_memoria_raw(
                shell,
                "consolidate",
                "profile-status",
                "run",
                "-ProfileId",
                "person:purocielo:test",
                "-WorkspaceRoot",
                str(workspace),
            )
            profile_status_dry_run_completed = run_memoria(
                shell,
                "consolidate",
                "profile-status",
                "dry-run",
                "-ProfileId",
                "person:purocielo:test",
                "-WorkspaceRoot",
                str(workspace),
            )
            db_path = workspace / "database" / "evidence.sqlite"
            store = SQLiteEvidenceStore(db_path)
            before_records = store.count("evidence_records")
            before_claims = store.count("evidence_claims")
            canonical_ledger_path = workspace / "risultati" / "runs" / "run-con-ledger-pipeline" / "mvp_consolidated_review_ledger.json"
            canonical_ledger_before = canonical_ledger_path.read_text(encoding="utf-8")
            run_preview_completed = run_memoria(shell, "consolidate", "run", "--preview", "-WorkspaceRoot", str(workspace))
            profile_status_run_completed = run_memoria(
                shell,
                "consolidate",
                "profile-status",
                "run",
                "--preview",
                "-ProfileId",
                "person:purocielo:test",
                "-WorkspaceRoot",
                str(workspace),
            )
            after_records = store.count("evidence_records")
            after_claims = store.count("evidence_claims")
            canonical_ledger_after = canonical_ledger_path.read_text(encoding="utf-8")
            session_exists_after_start = session_path.exists()
            session_payload = json.loads(session_path.read_text(encoding="utf-8-sig"))
            runs_dir = workspace / "risultati" / "runs"
            run_count = len([path for path in runs_dir.iterdir() if path.is_dir()])
            ledger_count = len(list(runs_dir.glob("*/mvp_consolidated_review_ledger.json")))
            cli_preview_outputs = list(runs_dir.glob("*/mvp_consolidated_review_ledger.cli_preview.*"))
            profile_status_outputs = list(runs_dir.glob("*/historian_review/profile_evidence_status.*.cli_preview.*"))
            profile_status_json_path = (
                workspace
                / "risultati"
                / "runs"
                / "run-con-ledger-pipeline"
                / "historian_review"
                / "profile_evidence_status.person-purocielo-test.cli_preview.json"
            )
            profile_status_md_path = profile_status_json_path.with_suffix(".md")
            profile_status_payload = json.loads(profile_status_json_path.read_text(encoding="utf-8-sig"))
            profile_status_markdown = profile_status_md_path.read_text(encoding="utf-8")
            verified_facts_outputs = list(runs_dir.glob("**/verified_facts*"))

        for completed in (discover_completed, status_before_start_completed):
            self.assertIn("Me.Mo.Ria consolidate discovery", completed.stdout)
            self.assertIn("Modalita: preview-only/read-only", completed.stdout)
            self.assertIn("Evidence store:", completed.stdout)
            self.assertIn("Presente: True", completed.stdout)
            self.assertIn("Run candidate: 2", completed.stdout)
            self.assertIn("Run con ledger consolidato: 1", completed.stdout)
            self.assertIn("run-con-ledger-pipeline | ledger=True", completed.stdout)
            self.assertIn("run-senza-ledger-pipeline | ledger=False", completed.stdout)
            self.assertIn("non crea verified_facts", completed.stdout)
        self.assertIn("Me.Mo.Ria consolidate start", start_completed.stdout)
        self.assertIn("Run attiva: run-con-ledger-pipeline", start_completed.stdout)
        self.assertIn("Motivo: ledger_json_available", start_completed.stdout)
        self.assertIn("memoria_consolidate_session.active.json", start_completed.stdout)
        self.assertIn("consolidate dry-run", start_completed.stdout)
        self.assertIn("consolidate run --preview", start_completed.stdout)
        self.assertIn("non rigenera ledger, non crea run e non importa nel DB", start_completed.stdout)
        self.assertIn("Me.Mo.Ria consolidate status", status_after_start_completed.stdout)
        self.assertIn("Run attiva: run-con-ledger-pipeline", status_after_start_completed.stdout)
        self.assertIn("Nessuna sessione consolidate attiva.", dry_run_before_start_completed.stdout)
        self.assertIn("consolidate start --auto", dry_run_before_start_completed.stdout)
        self.assertIn("Nessuna sessione consolidate attiva.", run_before_start_completed.stdout)
        self.assertIn("consolidate start --auto", run_before_start_completed.stdout)
        self.assertIn("Nessuna sessione consolidate attiva.", profile_status_before_start_completed.stdout)
        self.assertIn("consolidate start --auto", profile_status_before_start_completed.stdout)
        self.assertNotEqual(run_without_preview_completed.returncode, 0)
        self.assertIn("consolidate run usare --preview", run_without_preview_completed.stderr)
        self.assertNotEqual(profile_status_without_profile_completed.returncode, 0)
        self.assertIn("consolidate profile-status specificare -ProfileId", profile_status_without_profile_completed.stderr)
        self.assertNotEqual(profile_status_run_without_preview_completed.returncode, 0)
        self.assertIn("consolidate profile-status run usare --preview", profile_status_run_without_preview_completed.stderr)
        self.assertIn("Me.Mo.Ria consolidate dry-run", dry_run_after_start_completed.stdout)
        self.assertIn("build_mvp_consolidated_review_ledger.ps1", dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceDatabasePath", dry_run_after_start_completed.stdout)
        self.assertIn("-EvidenceSourceRunId", dry_run_after_start_completed.stdout)
        self.assertIn("run-con-ledger-pipeline", dry_run_after_start_completed.stdout)
        self.assertIn("mvp_consolidated_review_ledger.cli_preview.json", dry_run_after_start_completed.stdout)
        self.assertIn("non esegue il wrapper", dry_run_after_start_completed.stdout)
        self.assertIn("Me.Mo.Ria consolidate run", run_preview_completed.stdout)
        self.assertIn("Preview ledger generata.", run_preview_completed.stdout)
        self.assertIn("non importa nello store", run_preview_completed.stdout)
        self.assertIn("Me.Mo.Ria consolidate profile-status dry-run", profile_status_dry_run_completed.stdout)
        self.assertIn("build_evidence_store_profile_status.ps1", profile_status_dry_run_completed.stdout)
        self.assertIn("-ProfileId", profile_status_dry_run_completed.stdout)
        self.assertIn("person:purocielo:test", profile_status_dry_run_completed.stdout)
        self.assertIn("profile_evidence_status.person-purocielo-test.cli_preview.json", profile_status_dry_run_completed.stdout)
        self.assertIn("non esegue il wrapper", profile_status_dry_run_completed.stdout)
        self.assertIn("Me.Mo.Ria consolidate profile-status run", profile_status_run_completed.stdout)
        self.assertIn("Profile status preview generata.", profile_status_run_completed.stdout)
        self.assertIn("non scrive nello store", profile_status_run_completed.stdout)
        self.assertFalse(session_exists_before_start)
        self.assertTrue(session_exists_after_start)
        self.assertTrue(session_payload["preview_only"])
        self.assertEqual(session_payload["selected_run_id"], "run-con-ledger-pipeline")
        self.assertEqual(session_payload["discovery_reason"], "ledger_json_available")
        self.assertTrue(session_payload["selected_ledger_json"].endswith("mvp_consolidated_review_ledger.json"))
        self.assertEqual(run_count, 2)
        self.assertEqual(ledger_count, 1)
        self.assertEqual(len(cli_preview_outputs), 2)
        self.assertTrue(any(path.name.endswith(".cli_preview.json") for path in cli_preview_outputs))
        self.assertTrue(any(path.name.endswith(".cli_preview.md") for path in cli_preview_outputs))
        self.assertEqual(len(profile_status_outputs), 2)
        self.assertEqual(profile_status_payload["@type"], "EvidenceStoreProfileStatus")
        self.assertTrue(profile_status_payload["preview_only"])
        self.assertEqual(profile_status_payload["profile_id"], "person:purocielo:test")
        self.assertEqual(profile_status_payload["source_run_ids"], ["run-con-ledger-pipeline"])
        self.assertEqual(profile_status_payload["record_count"], 3)
        self.assertEqual(profile_status_payload["empty_result_diagnostics"], {})
        self.assertIn("candidate_document_person_link", profile_status_payload["counts_by_record_kind"])
        self.assertIn("candidate_evidence_claim", profile_status_payload["counts_by_record_kind"])
        self.assertIn("review_queue_item", profile_status_payload["counts_by_record_kind"])
        self.assertIn("Evidence Store profile status", profile_status_markdown)
        self.assertIn("person:purocielo:test", profile_status_markdown)
        self.assertNotIn("Diagnostica risultato vuoto", profile_status_markdown)
        self.assertEqual(before_records, after_records)
        self.assertEqual(before_claims, after_claims)
        self.assertEqual(canonical_ledger_before, canonical_ledger_after)
        self.assertEqual(verified_facts_outputs, [])

    def test_review_start_accepts_powershell_auto_switch(self) -> None:
        shell = powershell_exe()
        if shell is None:
            self.skipTest("PowerShell non disponibile")

        with workspace_temp_dir() as workspace:
            write_review_workspace(workspace)

            start_completed = run_memoria(shell, "review", "start", "-Auto", "-WorkspaceRoot", str(workspace))
            session_path = workspace / "database" / "memoria_review_session.active.json"
            session_payload = json.loads(session_path.read_text(encoding="utf-8-sig"))

        self.assertIn("Run attiva: run-forte-pipeline", start_completed.stdout)
        self.assertTrue(session_payload["preview_only"])
        self.assertEqual(session_payload["selected_run_id"], "run-forte-pipeline")


if __name__ == "__main__":
    unittest.main()
