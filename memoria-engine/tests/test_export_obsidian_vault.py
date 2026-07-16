from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.export_obsidian_vault import (
    export_mvp_pilot_obsidian_vault,
    export_obsidian_vault,
    export_profile_obsidian_vault,
)
from caduti_fonti_report.models import HistoricalEvent, PersonQuery, Place, SearchRun, SourceDocument, SourceResult
from caduti_fonti_report.person_profiles import profile_from_person_query, profile_to_jsonld
from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore


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


def populated_store(db_path: Path) -> SQLiteEvidenceStore:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    run = SearchRun(
        run_id="meta:prova-cwgc",
        timestamp="2026-04-26T16:55:03+00:00",
        input_file="risultati/prova_meta_cwgc.json",
        source_ids=["cwgc"],
    )
    store.insert_search_run(run)
    store.insert_person_query(run.run_id, PersonQuery(full_name="Panov Sergio", given_name="Sergio", family_name="Panov"))
    store.insert_source_result(
        run.run_id,
        SourceResult(
            source_id="cwgc",
            source_name="CWGC",
            status="search_url_ready",
            note="URL pronti",
            query="Panov Sergio",
            search_url="https://example.test/cwgc",
        ),
    )
    store.insert_source_document(
        run.run_id,
        SourceDocument(
            document_id="cwgc-doc-1",
            source_id="cwgc",
            title="CWGC ricerca 1",
            url="https://example.test/cwgc/1",
            access_date="2026-04-26T16:55:03+00:00",
            media_type="text/uri-list",
            metadata={"access_mode": "reference_only"},
        ),
    )
    store.insert_source_document(
        run.run_id,
        SourceDocument(
            document_id="cwgc-doc-2",
            source_id="cwgc",
            title="CWGC ricerca 2",
            url="https://example.test/cwgc/2",
            access_date="2026-04-26T16:55:03+00:00",
            media_type="text/uri-list",
            metadata={"access_mode": "reference_only"},
        ),
    )
    store.insert_event(
        HistoricalEvent(
            event_id="event:battaglia-purocielo",
            event_type="battle",
            label="Battaglia di Purocielo",
            description="Evento pilota non ancora revisionato.",
            date_start="1944-10-11",
            date_end="1944-10-12",
            place_labels=["Purocielo"],
            place_ids=["place:purocielo"],
            source_document_ids=["cwgc-doc-1"],
            evidence_claim_ids=[],
            review_status="draft",
            provenance="fixture:test",
        )
    )
    store.insert_place(
        Place(
            place_id="place:purocielo",
            preferred_label="Purocielo",
            place_type="locality",
            alternate_labels=["Puro Cielo"],
            description="Luogo pilota non ancora revisionato.",
            source_document_ids=["cwgc-doc-1"],
            evidence_claim_ids=[],
            review_status="draft",
            provenance="fixture:test",
        )
    )
    return store


def write_profile_index_fixture(root: Path) -> Path:
    profiles_dir = root / "person_profiles"
    profiles_dir.mkdir()
    profile = profile_from_person_query(
        PersonQuery(
            full_name="Guazzaloca Laura",
            given_name="Laura",
            family_name="Guazzaloca",
            death_date="novembre 1944",
            formation="infermiera partigiana",
        ),
        seed_source="fixture.csv",
        imported_at="2026-05-09T10:00:00+00:00",
    )
    payload = profile_to_jsonld(profile)
    payload["evidence_claim_ids"] = ["claim:death-cause"]
    payload["verified_facts"] = {
        "death.cause": {
            "value": "Esecuzione",
            "source_claim_ids": ["claim:death-cause"],
            "source_document_ids": ["doc:storia-memoria-bo:1"],
            "review_status": "reviewed",
            "provenance": "ProfilePatch:candidate-profile-update:death-cause",
        }
    }
    payload["conflicts"] = [
        {
            "field": "death.date",
            "current_value": "novembre 1944",
            "candidate_value": "23 novembre 1944",
            "review_status": "needs_review",
            "source_document_ids": ["doc:storia-memoria-bo:1"],
        }
    ]
    payload["next_research"] = ["Verificare documento originale."]
    payload["searched_sources"] = ["storia_memoria_bo"]
    profile_path = profiles_dir / "purocielo-guazzaloca-laura.jsonld"
    profile_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(
        json.dumps(
            {
                "@type": "PersonResearchProfileIndex",
                "count": 1,
                "profiles": [
                    {
                        "@id": "person:purocielo:guazzaloca-laura",
                        "file": "purocielo-guazzaloca-laura.jsonld",
                        "canonical_name": "Guazzaloca Laura",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return index_path


def write_mvp_pilot_summary_fixture(root: Path) -> Path:
    profiles_dir = root / "ricerche" / "person_profiles"
    profiles_dir.mkdir(parents=True)
    andreoli_profile = {
        "@type": "PersonResearchProfile",
        "profile_id": "person:purocielo:andreoli-dino",
        "identity": {
            "canonical_name": "Andreoli Dino",
            "given_name": "Dino",
            "family_name": "Andreoli",
            "name_forms": ["Andreoli Dino", "Andreoli", "Dino"],
        },
        "seed": {
            "source": "ricerche/caduti_purocielo.csv",
            "payload": {
                "fonti_richiamate": "Storia e Memoria; ANPI Bologna",
                "profilo_biografico": "Andreoli Dino compare nella memoria locale come partigiano della 36a Brigata.",
            },
        },
        "birth": {"date": "17 maggio 1920, San Lazzaro di Savena"},
        "death": {"date": "11 ottobre 1944, battaglia di Purocielo"},
        "formations": ["partigiano della 36a Brigata"],
        "events": ["Ricordato tra i caduti di Purocielo."],
        "places": ["San Lazzaro di Savena", "Purocielo"],
        "search_hints": [
            {
                "field": "identity.full_name",
                "value": "Andreoli Dino",
                "provenance": "seed.full_name",
                "review_status": "unreviewed",
            }
        ],
        "verified_facts": {},
    }
    guazzaloca_profile = {
        "@type": "PersonResearchProfile",
        "profile_id": "person:purocielo:guazzaloca-laura",
        "identity": {
            "canonical_name": "Guazzaloca Laura",
            "name_forms": ["Guazzaloca Laura", "Laura Guazzaloca"],
        },
        "seed": {"source": "ricerche/caduti_purocielo.csv", "payload": {}},
        "verified_facts": {},
    }
    andreoli_path = profiles_dir / "purocielo-andreoli-dino.jsonld"
    guazzaloca_path = profiles_dir / "purocielo-guazzaloca-laura.jsonld"
    andreoli_path.write_text(json.dumps(andreoli_profile, ensure_ascii=False, indent=2), encoding="utf-8")
    guazzaloca_path.write_text(json.dumps(guazzaloca_profile, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "@type": "MvpPilotSummary",
        "run_dir": "risultati/runs/test-mvp",
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "profile_count": 2,
        "document_count": 1,
        "candidate_document_person_link_count": 1,
        "candidate_evidence_claim_count": 1,
        "reviewable_document_signal_count": 2,
        "profiles": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "profile_source_file": str(andreoli_path),
            },
            {
                "profile_id": "person:purocielo:guazzaloca-laura",
                "canonical_name": "Guazzaloca Laura",
                "profile_source_file": str(guazzaloca_path),
            },
        ],
        "documents": [
            {
                "source_document_id": "doc-andreoli-1",
                "title": "Scheda Andreoli Dino",
                "document_class": "html_document",
                "quality_status": "ready_for_manual_review",
                "quality_path": "processed/doc-andreoli-1.quality.json",
                "review_status": "unreviewed",
            }
        ],
        "candidate_document_person_links": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "source_document_id": "doc-andreoli-1",
                "score": 1.0,
                "review_status": "unreviewed",
            }
        ],
        "candidate_evidence_claims": [
            {
                "@id": "candidate-evidence-claim:andreoli-birth",
                "profile_id": "person:purocielo:andreoli-dino",
                "field": "birth.date",
                "value": "17 maggio 1920",
                "source_document_id": "doc-andreoli-1",
                "review_status": "unreviewed",
            }
        ],
        "profile_readiness": [
            {
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "document_count": 1,
                "candidate_document_person_link_count": 1,
                "candidate_evidence_claim_count": 1,
                "reviewable_document_signal_count": 1,
                "readiness_status": "ready_for_review",
                "next_action": "Revisionare documenti, link e claim candidati.",
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_human_review",
            },
            {
                "profile_id": "person:purocielo:guazzaloca-laura",
                "canonical_name": "Guazzaloca Laura",
                "document_count": 0,
                "candidate_document_person_link_count": 0,
                "candidate_evidence_claim_count": 0,
                "reviewable_document_signal_count": 1,
                "readiness_status": "needs_signal_review",
                "next_action": "Revisionare piste documentali e valutare segmentazione per produrre claim candidati.",
                "review_status": "unreviewed",
                "publication_status": "not_publishable_without_human_review",
            },
        ],
        "reviewable_document_signals": [
            {
                "@type": "MvpProfileReviewableDocumentSignals",
                "profile_id": "person:purocielo:andreoli-dino",
                "canonical_name": "Andreoli Dino",
                "signal_count": 1,
                "signals": [
                    {
                        "@type": "ReviewableDocumentSignal",
                        "signal_type": "extracted_entity",
                        "source_document_id": "doc-andreoli-1",
                        "source_item_id": "extracted-entity:andreoli-formation",
                        "value": "36a Brigata",
                        "context": "Andreoli Dino opero nella 36a Brigata.",
                        "reasons": ["extracted_entity_unreviewed"],
                        "review_status": "unreviewed",
                    }
                ],
                "review_status": "unreviewed",
            },
            {
                "@type": "MvpProfileReviewableDocumentSignals",
                "profile_id": "person:purocielo:guazzaloca-laura",
                "canonical_name": "Guazzaloca Laura",
                "signal_count": 1,
                "signals": [
                    {
                        "@type": "ReviewableDocumentSignal",
                        "signal_type": "research_feedback_action",
                        "source_document_id": "doc-guazzaloca-1",
                        "source_item_id": "research-feedback-action:guazzaloca",
                        "value": "Guazzaloca Laura",
                        "context": "Guazzaloca Laura, Nascita: 28 gennaio 1920, Bologna.",
                        "reasons": ["research_feedback_action_unreviewed"],
                        "review_status": "unreviewed",
                    }
                ],
                "review_status": "unreviewed",
            },
        ],
        "document_intake_readiness": {
            "available": True,
            "local_run_dir": "risultati/runs/test-mvp-local",
            "input_processing_plan": {
                "available": True,
                "asset_count": 3,
                "action_counts": {
                    "html_document_ready": 1,
                    "image_ocr_required": 2,
                },
            },
            "metadata_extraction": {
                "available": True,
                "document_count": 3,
            },
            "text_extraction": {
                "available": True,
                "document_count": 3,
                "extracted_count": 1,
                "skipped_count": 2,
            },
            "ocr_batch": {
                "available": True,
                "summary": {
                    "processed": 1,
                    "skipped_existing_text": 1,
                    "skipped_missing_sidecar": 0,
                    "skipped_duplicate_output": 0,
                    "error": 0,
                },
            },
            "mvp_document_count": 1,
            "mvp_blockers": ["2 immagini richiedono controllo OCR prima della revisione storica."],
            "next_action": "Eseguire o correggere OCR batch sui documenti immagine prioritari.",
            "review_status": "unreviewed",
            "publication_status": "not_publishable_without_human_review",
        },
        "mvp_signal_diagnostics": {
            "@type": "MvpSignalDiagnostics",
            "document_count": 2,
            "estimated_unique_document_count": 1,
            "duplicate_document_group_count": 1,
            "duplicate_document_count": 1,
            "duplicate_document_groups": [
                {
                    "key_kind": "sha256",
                    "key_value": "same-hash",
                    "document_count": 2,
                    "source_document_ids": ["data_raw:doc-1", "documenti:doc-1"],
                    "review_status": "unreviewed",
                }
            ],
            "candidate_document_person_link_count": 2,
            "weak_nominal_link_count": 2,
            "candidate_evidence_claim_count": 1,
            "profiles_with_links_no_claims_count": 1,
            "profiles_with_links_no_claims": [
                {
                    "profile_id": "person:purocielo:guazzaloca-laura",
                    "canonical_name": "Guazzaloca Laura",
                    "candidate_document_person_link_count": 1,
                    "reviewable_document_signal_count": 1,
                    "readiness_status": "needs_signal_review",
                }
            ],
            "mvp_blockers": [
                "1 documenti sembrano duplicati o copie dello stesso contenuto.",
                "2 link persona-documento sono match nominali deboli.",
            ],
            "next_action": "Revisionare i gruppi duplicati e presentare il pacchetto usando i documenti unici stimati.",
            "review_status": "unreviewed",
            "publication_status": "not_publishable_without_human_review",
        },
        "pilot_package_scorecard": {
            "@type": "MvpPilotPackageScorecard",
            "package_status": "ready_with_document_intake_warnings",
            "profile_count": 2,
            "ready_for_review_profile_count": 1,
            "blocked_profile_count": 1,
            "readiness_status_counts": {
                "ready_for_review": 1,
                "needs_signal_review": 1,
            },
            "document_count": 1,
            "candidate_document_person_link_count": 1,
            "candidate_evidence_claim_count": 1,
            "reviewable_document_signal_count": 2,
            "minimum_review_item_count": 7,
            "document_intake_blocker_count": 1,
            "top_blockers": ["2 immagini richiedono controllo OCR prima della revisione storica."],
            "next_action": "Revisionare le schede pronte e pianificare i blocchi documentali residui.",
            "review_status": "unreviewed",
            "publication_status": "not_publishable_without_human_review",
        },
        "warnings": ["Serve revisione umana prima della pubblicazione."],
    }
    summary_path = root / "mvp_pilot_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary_path


class ExportObsidianVaultTests(unittest.TestCase):
    def test_export_obsidian_vault_creates_minimal_vault(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            populated_store(tmp_dir / "evidence.sqlite")
            output_dir = tmp_dir / "vault" / "ResistenzaWiki"

            result = export_obsidian_vault(
                db_path=tmp_dir / "evidence.sqlite",
                run_id="meta:prova-cwgc",
                output_dir=output_dir,
            )
            person_text = (output_dir / "01_Persone" / "panov-sergio.md").read_text(encoding="utf-8")
            doc_text = (output_dir / "02_Documenti" / "cwgc-doc-1.md").read_text(encoding="utf-8")
            event_text = (output_dir / "03_Eventi" / "event-battaglia-purocielo.md").read_text(encoding="utf-8")
            place_text = (output_dir / "04_Luoghi" / "place-purocielo.md").read_text(encoding="utf-8")
            evidence_text = (output_dir / "07_Evidenze" / "README.md").read_text(encoding="utf-8")
            log_text = (output_dir / "09_Log_ricerca" / "meta-prova-cwgc.md").read_text(encoding="utf-8")

        self.assertEqual(result["run_id"], "meta:prova-cwgc")
        self.assertIn("type: person", person_text)
        self.assertIn("# Panov Sergio", person_text)
        self.assertIn("[[../02_Documenti/cwgc-doc-1]]", person_text)
        self.assertIn("<!-- BEGIN AUTO-GENERATED -->", person_text)
        self.assertIn("<!-- BEGIN EDITORIAL NOTES -->", person_text)
        self.assertIn("document_id: \"cwgc-doc-1\"", doc_text)
        self.assertIn("Access mode: reference_only", doc_text)
        self.assertIn("type: historical_event", event_text)
        self.assertIn("event_id: \"event:battaglia-purocielo\"", event_text)
        self.assertIn("event_type: \"battle\"", event_text)
        self.assertIn("review_status: \"draft\"", event_text)
        self.assertIn("[[../02_Documenti/cwgc-doc-1]]", event_text)
        self.assertIn("[[../04_Luoghi/place-purocielo]]", event_text)
        self.assertIn("Nessuna Participation creata da questo export.", event_text)
        self.assertIn("type: place", place_text)
        self.assertIn("place_id: \"place:purocielo\"", place_text)
        self.assertIn("place_type: \"locality\"", place_text)
        self.assertIn("review_status: \"draft\"", place_text)
        self.assertIn("Variante: Puro Cielo", place_text)
        self.assertIn("[[../02_Documenti/cwgc-doc-1]]", place_text)
        self.assertIn("Nessuna relazione persona-luogo, evento-luogo forte", place_text)
        self.assertIn("Nessuna EvidenceClaim estratta per questa run.", evidence_text)
        self.assertIn("Log ricerca meta:prova-cwgc", log_text)
        self.assertIn("verifica manuale richiesta", log_text)

    def test_export_obsidian_vault_preserves_editorial_notes(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            populated_store(tmp_dir / "evidence.sqlite")
            output_dir = tmp_dir / "vault" / "ResistenzaWiki"
            person_dir = output_dir / "01_Persone"
            person_dir.mkdir(parents=True)
            person_path = person_dir / "panov-sergio.md"
            person_path.write_text(
                "\n".join(
                    [
                        "# Vecchia scheda",
                        "<!-- BEGIN EDITORIAL NOTES -->",
                        "Nota curatoriale da preservare.",
                        "<!-- END EDITORIAL NOTES -->",
                    ]
                ),
                encoding="utf-8",
            )

            export_obsidian_vault(
                db_path=tmp_dir / "evidence.sqlite",
                run_id="meta:prova-cwgc",
                output_dir=output_dir,
            )
            person_text = person_path.read_text(encoding="utf-8")

        self.assertIn("Nota curatoriale da preservare.", person_text)
        self.assertIn("# Panov Sergio", person_text)

    def test_missing_run_raises_controlled_error_without_creating_output_dir(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            SQLiteEvidenceStore(tmp_dir / "evidence.sqlite").init_schema()
            output_dir = tmp_dir / "vault" / "ResistenzaWiki"

            with self.assertRaises(ValueError):
                export_obsidian_vault(
                    db_path=tmp_dir / "evidence.sqlite",
                    run_id="missing-run",
                    output_dir=output_dir,
                )

            exists = output_dir.exists()

        self.assertFalse(exists)

    def test_export_profile_obsidian_vault_writes_review_profile_without_promoting_seed(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_index_fixture(tmp_dir)
            output_dir = tmp_dir / "vault" / "ResistenzaWiki"

            result = export_profile_obsidian_vault(
                profiles_index=index_path,
                output_dir=output_dir,
                profile_id="person:purocielo:guazzaloca-laura",
            )
            person_text = (output_dir / "01_Persone" / "guazzaloca-laura.md").read_text(encoding="utf-8")

        self.assertEqual(result["profiles_exported"], 1)
        self.assertIn("type: person_research_profile", person_text)
        self.assertIn("profile_id: \"person:purocielo:guazzaloca-laura\"", person_text)
        self.assertIn("## Fatti revisionati", person_text)
        self.assertIn("`death.cause`: Esecuzione | stato=reviewed", person_text)
        self.assertIn("`claim:death-cause`", person_text)
        self.assertIn("## Conflitti aperti", person_text)
        self.assertIn("candidato `23 novembre 1944`", person_text)
        self.assertIn("## Indizi operativi non pubblicabili", person_text)
        self.assertIn("il seed resta un indizio operativo", person_text)
        self.assertNotIn("maestra elementare", person_text)

    def test_export_profile_obsidian_vault_preserves_editorial_notes(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            index_path = write_profile_index_fixture(tmp_dir)
            output_dir = tmp_dir / "vault" / "ResistenzaWiki"
            person_dir = output_dir / "01_Persone"
            person_dir.mkdir(parents=True)
            person_path = person_dir / "guazzaloca-laura.md"
            person_path.write_text(
                "\n".join(
                    [
                        "# Vecchia scheda",
                        "<!-- BEGIN EDITORIAL NOTES -->",
                        "Nota umana da preservare.",
                        "<!-- END EDITORIAL NOTES -->",
                    ]
                ),
                encoding="utf-8",
            )

            export_profile_obsidian_vault(profiles_index=index_path, output_dir=output_dir)
            person_text = person_path.read_text(encoding="utf-8")

        self.assertIn("Nota umana da preservare.", person_text)
        self.assertIn("# Guazzaloca Laura", person_text)

    def test_export_mvp_pilot_obsidian_vault_writes_review_pack_without_promoting_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_path = write_mvp_pilot_summary_fixture(tmp_dir)
            review_summary_path = tmp_dir / "historian_review" / "review_decisions_summary.json"
            review_summary_path.parent.mkdir(parents=True)
            review_summary_path.write_text(
                json.dumps(
                    {
                        "@type": "MvpReviewDecisionsSummary",
                        "review_session": {
                            "@type": "MvpReviewSession",
                            "session_status": "in_review",
                            "profile_count": 2,
                            "ready_for_curator_review_count": 0,
                            "profiles": [
                                {
                                    "@type": "MvpReviewSessionProfile",
                                    "profile_id": "person:purocielo:andreoli-dino",
                                    "session_status": "in_review",
                                    "item_count": 4,
                                    "accepted_count": 1,
                                    "pending_count": 3,
                                    "invalid_count": 0,
                                },
                                {
                                    "@type": "MvpReviewSessionProfile",
                                    "profile_id": "person:purocielo:guazzaloca-laura",
                                    "session_status": "not_started",
                                    "item_count": 3,
                                    "accepted_count": 0,
                                    "pending_count": 3,
                                    "invalid_count": 0,
                                },
                            ],
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            output_dir = tmp_dir / "vault" / "MvpPilotReview"

            result = export_mvp_pilot_obsidian_vault(
                summary_json=summary_path,
                output_dir=output_dir,
                limit=1,
                review_queue_md=tmp_dir / "historian_review" / "review_queue.md",
                review_decisions_summary=review_summary_path,
            )
            person_text = (output_dir / "01_Persone" / "andreoli-dino.md").read_text(encoding="utf-8")
            candidate_text = (output_dir / "40_Publication_Candidates" / "andreoli-dino.md").read_text(encoding="utf-8")
            document_text = (output_dir / "02_Documenti" / "doc-andreoli-1.md").read_text(encoding="utf-8")
            evidence_text = (output_dir / "07_Evidenze" / "README.md").read_text(encoding="utf-8")
            dashboard_text = (output_dir / "10_Output" / "MVP_Pilot_Review.md").read_text(encoding="utf-8")
            brief_text = (output_dir / "10_Output" / "mvp_curatorial_brief.md").read_text(encoding="utf-8")

        self.assertEqual(result["profiles_exported"], 1)
        self.assertIn("type: mvp_pilot_person_review", person_text)
        self.assertIn("profile_id: \"person:purocielo:andreoli-dino\"", person_text)
        self.assertIn("Claim candidati", person_text)
        self.assertIn("Piste documentali da revisionare", person_text)
        self.assertIn("extracted_entity", person_text)
        self.assertIn("birth.date", person_text)
        self.assertIn("Stato scheda pilota: `ready_for_review`", person_text)
        self.assertIn("Stato review storica", person_text)
        self.assertIn("Stato sessione: `in_review`", person_text)
        self.assertIn("Item review: `4`", person_text)
        self.assertIn("Profilo operativo JSON-LD", person_text)
        self.assertIn("17 maggio 1920, San Lazzaro di Savena", person_text)
        self.assertIn("partigiano della 36a Brigata", person_text)
        self.assertIn("Search hints principali", person_text)
        self.assertIn("seed e indizi operativi", person_text)
        self.assertIn("Scheda di revisione, non scheda pubblicabile", person_text)
        self.assertIn("type: mvp_pilot_document_review", document_text)
        self.assertIn("source_document_id: \"doc-andreoli-1\"", document_text)
        self.assertIn("candidate-evidence-claim:andreoli-birth", evidence_text)
        self.assertIn("MVP Pilot Review", dashboard_text)
        self.assertIn("Profili esportati: 1", dashboard_text)
        self.assertIn("Scorecard pacchetto MVP", dashboard_text)
        self.assertIn("ready_with_document_intake_warnings", dashboard_text)
        self.assertIn("Piste documentali revisionabili: 2", dashboard_text)
        self.assertIn("Item minimi di revisione: `7`", dashboard_text)
        self.assertIn("Stato schede pilota", dashboard_text)
        self.assertIn("Stato ingest documentale", dashboard_text)
        self.assertIn("image_ocr_required", dashboard_text)
        self.assertIn("Testi estratti: `1` / `3`", dashboard_text)
        self.assertIn("Diagnostica segnale MVP", dashboard_text)
        self.assertIn("Documenti unici stimati: `1`", dashboard_text)
        self.assertIn("Link nominali deboli: `2` / `2`", dashboard_text)
        self.assertIn("Duplicati da revisionare", dashboard_text)
        self.assertIn("Prossime decisioni", dashboard_text)
        self.assertIn("review_queue.md", dashboard_text)
        self.assertIn("review_decisions_summary.json", dashboard_text)
        self.assertIn("Sessione review storici", dashboard_text)
        self.assertIn("Pronti per revisione curatoriale: `0`", dashboard_text)
        self.assertIn("Schede candidate", dashboard_text)
        self.assertIn("40_Publication_Candidates", dashboard_text)
        self.assertIn("in_review", dashboard_text)
        self.assertIn("ready_for_review", dashboard_text)
        self.assertIn("type: publication_card_candidate", candidate_text)
        self.assertIn("Stato candidatura: `needs_review`", candidate_text)
        self.assertIn("Scheda di revisione", candidate_text)
        self.assertIn("Evidenze candidate", candidate_text)
        self.assertIn("birth.date", candidate_text)
        self.assertIn("Nessun claim candidato e' trattato come fatto verificato.", candidate_text)
        self.assertIn("type: mvp_curatorial_brief", brief_text)
        self.assertIn("Brief curatoriale MVP Purocielo", brief_text)
        self.assertIn("Dashboard operativa", brief_text)
        self.assertIn("Schede candidate", brief_text)
        self.assertIn("Sessione storici", brief_text)
        self.assertIn("Blocchi documentali", brief_text)
        self.assertIn("Segnale MVP per finanziamento", brief_text)
        self.assertIn("Profili con link ma zero claim: `1`", brief_text)
        self.assertIn("Nessun claim candidato e' promosso a fatto verificato.", brief_text)
        combined = person_text + candidate_text + document_text + evidence_text + dashboard_text + brief_text
        self.assertNotIn("ProfilePatch", combined)
        self.assertNotIn("verified_facts", combined)

    def test_export_mvp_pilot_obsidian_vault_shows_incomplete_profile_readiness(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_path = write_mvp_pilot_summary_fixture(tmp_dir)
            output_dir = tmp_dir / "vault" / "MvpPilotReview"

            result = export_mvp_pilot_obsidian_vault(
                summary_json=summary_path,
                output_dir=output_dir,
                limit=2,
            )
            dashboard_text = (output_dir / "10_Output" / "MVP_Pilot_Review.md").read_text(encoding="utf-8")
            person_text = (output_dir / "01_Persone" / "guazzaloca-laura.md").read_text(encoding="utf-8")

        self.assertEqual(result["profiles_exported"], 2)
        self.assertIn("needs_signal_review", dashboard_text)
        self.assertIn("Revisionare piste documentali", dashboard_text)
        self.assertIn("Stato scheda pilota: `needs_signal_review`", person_text)
        self.assertIn("Guazzaloca Laura, Nascita", person_text)
        self.assertNotIn("verified_facts", dashboard_text + person_text)

    def test_export_mvp_pilot_obsidian_vault_preserves_editorial_notes(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            summary_path = write_mvp_pilot_summary_fixture(tmp_dir)
            output_dir = tmp_dir / "vault" / "MvpPilotReview"
            person_dir = output_dir / "01_Persone"
            person_dir.mkdir(parents=True)
            person_path = person_dir / "andreoli-dino.md"
            person_path.write_text(
                "\n".join(
                    [
                        "# Vecchia scheda",
                        "<!-- BEGIN EDITORIAL NOTES -->",
                        "Nota curatoriale MVP da preservare.",
                        "<!-- END EDITORIAL NOTES -->",
                    ]
                ),
                encoding="utf-8",
            )

            export_mvp_pilot_obsidian_vault(summary_json=summary_path, output_dir=output_dir, limit=1)
            person_text = person_path.read_text(encoding="utf-8")

        self.assertIn("Nota curatoriale MVP da preservare.", person_text)
        self.assertIn("# Andreoli Dino", person_text)


if __name__ == "__main__":
    unittest.main()
