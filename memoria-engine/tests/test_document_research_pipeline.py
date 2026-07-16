from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.mvp_pilot_summary import (  # noqa: E402
    _document_intake_readiness,
    build_mvp_pilot_summary,
)
from caduti_fonti_report.document_analysis.pipeline_runner import run_document_research_pipeline  # noqa: E402


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


def write_profile_index(root_dir: Path) -> Path:
    profiles_dir = root_dir / "profiles"
    profiles_dir.mkdir()
    profile = {
        "@type": "PersonResearchProfile",
        "@id": "person:purocielo:andreoli-dino",
        "profile_id": "person:purocielo:andreoli-dino",
        "identity": {
            "canonical_name": "Andreoli Dino",
            "given_name": "Dino",
            "family_name": "Andreoli",
            "aliases": [],
            "name_forms": ["Andreoli Dino"],
        },
        "seed": {"source": "test", "source_id": "", "imported_at": "", "payload": {}},
        "birth": {},
        "death": {},
        "formations": [],
        "events": [],
        "places": [],
        "search_hints": [],
        "evidence_claim_ids": [],
        "verified_facts": {},
        "conflicts": [],
        "searched_sources": [],
        "next_research": [],
        "metadata": {},
    }
    (profiles_dir / "purocielo-andreoli-dino.jsonld").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    index = {
        "@type": "ca:PersonResearchProfileIndex",
        "profiles": [
            {
                "@id": "person:purocielo:andreoli-dino",
                "file": "purocielo-andreoli-dino.jsonld",
                "canonical_name": "Andreoli Dino",
            }
        ],
    }
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def write_research_dir(root_dir: Path) -> Path:
    research_dir = root_dir / "remote" / "ricerche"
    profiles_dir = research_dir / "person_profiles"
    places_dir = research_dir / "places"
    profiles_dir.mkdir(parents=True)
    places_dir.mkdir(parents=True)

    profile = {
        "@type": "PersonResearchProfile",
        "@id": "person:purocielo:andreoli-dino",
        "profile_id": "person:purocielo:andreoli-dino",
        "identity": {
            "canonical_name": "Andreoli Dino",
            "given_name": "Dino",
            "family_name": "Andreoli",
            "aliases": [],
            "name_forms": ["Andreoli Dino"],
        },
        "seed": {"source": "test", "source_id": "", "imported_at": "", "payload": {}},
        "birth": {},
        "death": {},
        "formations": [],
        "events": [],
        "places": [],
        "search_hints": [],
        "evidence_claim_ids": [],
        "verified_facts": {},
        "conflicts": [],
        "searched_sources": [],
        "next_research": [],
        "metadata": {},
    }
    (profiles_dir / "purocielo-andreoli-dino.jsonld").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (profiles_dir / "purocielo.index.jsonld").write_text(
        json.dumps(
            {
                "@type": "ca:PersonResearchProfileIndex",
                "profiles": [
                    {
                        "@id": "person:purocielo:andreoli-dino",
                        "file": "purocielo-andreoli-dino.jsonld",
                        "canonical_name": "Andreoli Dino",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (places_dir / "purocielo.jsonld").write_text(
        json.dumps(
            {
                "@type": "PlaceResearchIdentity",
                "@id": "place:camalanca:purocielo",
                "place_id": "place:camalanca:purocielo",
                "preferred_label": "Purocielo",
                "alternate_labels": [],
                "review_status": "unreviewed",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (places_dir / "places.index.jsonld").write_text(
        json.dumps(
            {
                "@type": "PlaceResearchIdentityIndex",
                "places": [
                    {
                        "@id": "place:camalanca:purocielo",
                        "file": "purocielo.jsonld",
                        "preferred_label": "Purocielo",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (research_dir / "camalanca_fonti.yaml").write_text("sources: []\n", encoding="utf-8")
    return research_dir


def write_processed_document(root_dir: Path) -> Path:
    processed_dir = root_dir / "processed"
    source_dir = processed_dir / "camalanca_html"
    source_dir.mkdir(parents=True)
    metadata = {
        "@type": "ProcessedDocumentMetadata",
        "source_id": "camalanca_html",
        "source_document_id": "doc-1",
        "title": "Scheda Andreoli Dino",
        "document_class": "html_document",
        "media_type": "text/html",
        "raw_file": "data/raw/test/doc-1.html",
        "sha256": "abc123",
        "url": "https://example.test/doc-1",
        "archival_reference": "Test reference",
        "access_date": "2026-05-17",
        "claim_eligible": True,
        "review_status": "unreviewed",
    }
    text = {
        "@type": "ProcessedDocumentText",
        "source_id": "camalanca_html",
        "source_document_id": "doc-1",
        "title": "Scheda Andreoli Dino",
        "document_class": "html_document",
        "text_status": "extracted",
        "text": (
            "Andreoli Dino nacque a Bologna. "
            "Nato il 17 maggio 1920 a San Lazzaro di Savena. "
            "Opero nella 36a Brigata Bianconcini Garibaldi."
        ),
        "text_length": 129,
        "metadata_file": str(source_dir / "doc-1.metadata.json"),
        "review_status": "unreviewed",
    }
    (source_dir / "doc-1.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (source_dir / "doc-1.text.json").write_text(json.dumps(text, ensure_ascii=False, indent=2), encoding="utf-8")
    mentions = {
        "@type": "DocumentMentionCandidateDocument",
        "source_id": "camalanca_html",
        "source_document_id": "doc-1",
        "segments_file": str(source_dir / "doc-1.weak-segments.json"),
        "review_status": "unreviewed",
        "mention_count": 2,
        "mentions": [
            {
                "@type": "PersonMentionCandidate",
                "@id": "document-mention-candidate:person-andreoli-dino",
                "mention_id": "document-mention-candidate:person-andreoli-dino",
                "mention_kind": "person",
                "value": "Andreoli Dino",
                "normalized_value": "andreoli dino",
                "source_id": "camalanca_html",
                "source_document_id": "doc-1",
                "chunk_id": "physical-document-chunk:doc-1:1",
                "chunk_index": 1,
                "weak_segment_id": "weak-document-segment:doc-1:1",
                "context": "Andreoli Dino a Purocielo",
                "confidence": 0.62,
                "warnings": ["mention_candidate_not_verified_fact"],
                "candidate_profile_id": "",
                "review_status": "unreviewed",
            },
            {
                "@type": "PlaceMentionCandidate",
                "@id": "document-mention-candidate:place-purocielo",
                "mention_id": "document-mention-candidate:place-purocielo",
                "mention_kind": "place",
                "value": "Purocielo",
                "normalized_value": "purocielo",
                "source_id": "camalanca_html",
                "source_document_id": "doc-1",
                "chunk_id": "physical-document-chunk:doc-1:1",
                "chunk_index": 1,
                "weak_segment_id": "weak-document-segment:doc-1:1",
                "context": "Andreoli Dino a Purocielo",
                "confidence": 0.66,
                "warnings": ["mention_candidate_not_verified_fact"],
                "candidate_place_id": "",
                "review_status": "unreviewed",
            },
        ],
    }
    (source_dir / "doc-1.mentions.json").write_text(json.dumps(mentions, ensure_ascii=False, indent=2), encoding="utf-8")
    return processed_dir


class DocumentResearchPipelineTests(unittest.TestCase):
    def test_mvp_summary_includes_local_document_intake_readiness(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            processed_dir = write_processed_document(tmp_dir)
            profiles_index = write_profile_index(tmp_dir)
            results_dir = tmp_dir / "risultati"
            manifest = run_document_research_pipeline(
                run_id="test-run-intake",
                processed_dir=processed_dir,
                results_dir=results_dir,
                profiles_index=profiles_index,
                sources_yaml=tmp_dir / "missing-sources.yaml",
                skip_online=True,
                similarity_threshold=0.1,
            )
            run_dir = results_dir / "runs" / "test-run-intake"
            local_run_dir = results_dir / "runs" / "test-run-local"
            local_document_dir = local_run_dir / "document_analysis"
            local_document_dir.mkdir(parents=True)
            (local_document_dir / "input_processing_plan.json").write_text(
                json.dumps(
                    {
                        "@type": "InputProcessingPlan",
                        "root_dir": str(tmp_dir / "raw"),
                        "asset_count": 3,
                        "action_counts": {
                            "html_document_ready": 1,
                            "image_ocr_required": 2,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (local_document_dir / "ocr_batch_report.json").write_text(
                json.dumps(
                    {
                        "@type": "DocumentOcrBatchReport",
                        "summary": {
                            "total": 2,
                            "processed": 1,
                            "skipped_existing_text": 1,
                            "error": 0,
                        },
                        "log_file": str(local_document_dir / "ocr_batch.log"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (local_document_dir / "document_text_extraction.json").write_text(
                json.dumps(
                    {
                        "@type": "ProcessedDocumentTextSet",
                        "document_count": 3,
                        "extracted_count": 1,
                        "skipped_count": 2,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (local_document_dir / "document_metadata_extraction.json").write_text(
                json.dumps(
                    {
                        "@type": "ProcessedDocumentMetadataSet",
                        "document_count": 3,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = build_mvp_pilot_summary(
                run_dir=run_dir,
                local_run_dir=local_run_dir,
                profiles_index=profiles_index,
                output_json=run_dir / "document_analysis" / "mvp_pilot_summary.with-intake.json",
                output_md=run_dir / "document_analysis" / "mvp_pilot_summary.with-intake.md",
            )
            markdown = (run_dir / "document_analysis" / "mvp_pilot_summary.with-intake.md").read_text(encoding="utf-8")

        intake = summary["document_intake_readiness"]
        self.assertTrue(intake["available"])
        self.assertEqual(intake["input_processing_plan"]["asset_count"], 3)
        self.assertEqual(intake["input_processing_plan"]["action_counts"]["image_ocr_required"], 2)
        self.assertEqual(intake["ocr_batch"]["summary"]["processed"], 1)
        self.assertEqual(intake["text_extraction"]["extracted_count"], 1)
        self.assertEqual(summary["pilot_package_scorecard"]["@type"], "MvpPilotPackageScorecard")
        self.assertEqual(summary["pilot_package_scorecard"]["package_status"], "ready_for_human_review")
        self.assertGreaterEqual(summary["pilot_package_scorecard"]["minimum_review_item_count"], 1)
        self.assertIn("Scorecard pacchetto MVP", markdown)
        self.assertIn("ready_for_human_review", markdown)
        self.assertIn("Stato ingest documentale", markdown)
        self.assertIn("image_ocr_required", markdown)
        self.assertIn("OCR batch", markdown)
        self.assertNotIn("verified_facts", json.dumps(summary))

    def test_mvp_summary_does_not_block_on_non_claim_eligible_support_images(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            processed_dir = write_processed_document(tmp_dir)
            profiles_index = write_profile_index(tmp_dir)
            results_dir = tmp_dir / "risultati"
            run_document_research_pipeline(
                run_id="test-run-support-images",
                processed_dir=processed_dir,
                results_dir=results_dir,
                profiles_index=profiles_index,
                sources_yaml=tmp_dir / "missing-sources.yaml",
                skip_online=True,
                similarity_threshold=0.1,
            )
            run_dir = results_dir / "runs" / "test-run-support-images"
            local_run_dir = results_dir / "runs" / "test-run-local-support-images"
            local_document_dir = local_run_dir / "document_analysis"
            local_document_dir.mkdir(parents=True)
            (local_document_dir / "input_processing_plan.json").write_text(
                json.dumps(
                    {
                        "@type": "InputProcessingPlan",
                        "root_dir": str(tmp_dir / "raw"),
                        "asset_count": 3,
                        "action_counts": {
                            "html_document_ready": 1,
                            "image_ocr_required": 2,
                        },
                        "assets": [
                            {
                                "@type": "InputProcessingPlanAsset",
                                "source_document_id": "image:front",
                                "raw_file": "support/front.jpg",
                                "recommended_action": "image_ocr_required",
                            },
                            {
                                "@type": "InputProcessingPlanAsset",
                                "source_document_id": "image:back",
                                "raw_file": "support/back.jpg",
                                "recommended_action": "image_ocr_required",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (local_document_dir / "document_text_extraction.json").write_text(
                json.dumps(
                    {
                        "@type": "ProcessedDocumentTextSet",
                        "document_count": 3,
                        "extracted_count": 1,
                        "skipped_count": 2,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (local_document_dir / "document_metadata_extraction.json").write_text(
                json.dumps(
                    {
                        "@type": "ProcessedDocumentMetadataSet",
                        "document_count": 3,
                        "documents": [
                            {
                                "source_document_id": "image:front",
                                "document_class": "image_scan",
                                "claim_eligible": False,
                                "raw_file": "support/front.jpg",
                            },
                            {
                                "source_document_id": "image:back",
                                "document_class": "image_scan",
                                "claim_eligible": False,
                                "raw_file": "support/back.jpg",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = build_mvp_pilot_summary(
                run_dir=run_dir,
                local_run_dir=local_run_dir,
                profiles_index=profiles_index,
                output_md=run_dir / "document_analysis" / "mvp_pilot_summary.support-images.md",
            )
            markdown = (run_dir / "document_analysis" / "mvp_pilot_summary.support-images.md").read_text(
                encoding="utf-8"
            )

        intake = summary["document_intake_readiness"]
        image_readiness = intake["image_ocr_readiness"]
        self.assertEqual(image_readiness["support_image_count"], 2)
        self.assertEqual(image_readiness["blocking_image_count"], 0)
        self.assertEqual(image_readiness["unknown_image_count"], 0)
        self.assertFalse(any("richiedono OCR prioritario" in blocker for blocker in intake["mvp_blockers"]))
        self.assertEqual(intake["mvp_blockers"], [])
        self.assertIn("claim_eligible=false non bloccano", " ".join(intake["warnings"]))
        self.assertIn("Immagini di supporto", markdown)

    def test_document_intake_keeps_unknown_ocr_images_as_blockers(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            local_run_dir = tmp_dir / "runs" / "test-run-local-unknown-image"
            local_document_dir = local_run_dir / "document_analysis"
            local_document_dir.mkdir(parents=True)
            (local_document_dir / "input_processing_plan.json").write_text(
                json.dumps(
                    {
                        "@type": "InputProcessingPlan",
                        "root_dir": str(tmp_dir / "raw"),
                        "asset_count": 1,
                        "action_counts": {"image_ocr_required": 1},
                        "assets": [
                            {
                                "@type": "InputProcessingPlanAsset",
                                "source_document_id": "image:unknown",
                                "raw_file": "unknown/page.jpg",
                                "recommended_action": "image_ocr_required",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (local_document_dir / "document_text_extraction.json").write_text(
                json.dumps(
                    {"@type": "ProcessedDocumentTextSet", "document_count": 1, "extracted_count": 1, "skipped_count": 0},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (local_document_dir / "document_metadata_extraction.json").write_text(
                json.dumps(
                    {"@type": "ProcessedDocumentMetadataSet", "document_count": 1, "documents": []},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            intake = _document_intake_readiness(local_run_dir=local_run_dir, mvp_document_count=1)

        self.assertEqual(intake["image_ocr_readiness"]["unknown_image_count"], 1)
        self.assertTrue(any("1 immagini richiedono OCR prioritario" in blocker for blocker in intake["mvp_blockers"]))

    def test_mvp_summary_includes_signal_diagnostics_for_duplicates_and_weak_links(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            run_dir = tmp_dir / "risultati" / "runs" / "test-run-signal-diagnostics"
            document_dir = run_dir / "document_analysis"
            document_dir.mkdir(parents=True)
            (document_dir / "document_quality_assessment.json").write_text(
                json.dumps(
                    {
                        "@type": "DocumentQualityAssessmentSet",
                        "documents": [
                            {
                                "source_document_id": "data_raw:doc-1",
                                "title": "Scheda Andreoli Dino",
                                "raw_file": "documenti/scheda-andreoli.docx",
                                "sha256": "same-hash",
                                "document_class": "word_document",
                                "quality_status": "ready_for_manual_review",
                                "review_status": "unreviewed",
                            },
                            {
                                "source_document_id": "documenti:doc-1",
                                "title": "Scheda Andreoli Dino copia",
                                "raw_file": "documenti/scheda-andreoli-copia.docx",
                                "sha256": "same-hash",
                                "document_class": "word_document",
                                "quality_status": "ready_for_manual_review",
                                "review_status": "unreviewed",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (document_dir / "candidate_document_person_links.json").write_text(
                json.dumps(
                    {
                        "@type": "CandidateDocumentPersonLinkSet",
                        "candidate_document_person_links": [
                            {
                                "@id": "candidate-document-person-link:weak-andreoli",
                                "profile_id": "person:purocielo:andreoli-dino",
                                "matched_name": "Andreoli Dino",
                                "match_kind": "canonical_name",
                                "source_document_id": "data_raw:doc-1",
                                "context": "Andreoli Dino",
                                "score": 0.5,
                                "reasons": ["exact_canonical_name_match"],
                                "review_status": "unreviewed",
                            },
                            {
                                "@id": "candidate-document-person-link:weak-andreoli-copy",
                                "profile_id": "person:purocielo:andreoli-dino",
                                "matched_name": "Andreoli Dino",
                                "match_kind": "canonical_name",
                                "source_document_id": "documenti:doc-1",
                                "context": "Andreoli Dino",
                                "score": 0.5,
                                "reasons": ["exact_canonical_name_match"],
                                "review_status": "unreviewed",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (document_dir / "candidate_evidence_claims.json").write_text(
                json.dumps(
                    {
                        "@type": "CandidateEvidenceClaimSet",
                        "candidate_evidence_claims": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = build_mvp_pilot_summary(
                run_dir=run_dir,
                profiles_index=profiles_index,
                output_md=document_dir / "mvp_pilot_summary.md",
            )
            markdown = (document_dir / "mvp_pilot_summary.md").read_text(encoding="utf-8")

        diagnostics = summary["mvp_signal_diagnostics"]
        self.assertEqual(diagnostics["@type"], "MvpSignalDiagnostics")
        self.assertEqual(diagnostics["document_count"], 2)
        self.assertEqual(diagnostics["estimated_unique_document_count"], 1)
        self.assertEqual(diagnostics["duplicate_document_group_count"], 1)
        self.assertEqual(diagnostics["weak_nominal_link_count"], 2)
        self.assertEqual(diagnostics["profiles_with_links_no_claims_count"], 1)
        self.assertIn("documenti sembrano duplicati", " ".join(diagnostics["mvp_blockers"]))
        self.assertIn("Tutti i link persona-documento sono match nominali deboli", " ".join(diagnostics["mvp_blockers"]))
        self.assertIn("Diagnostica segnale MVP", markdown)
        self.assertIn("Documenti unici stimati", markdown)
        self.assertIn("Link nominali deboli", markdown)
        self.assertIn("Profili con link ma zero claim", markdown)
        self.assertNotIn("verified_facts", json.dumps(summary))

    def test_mvp_summary_keeps_reviewable_signals_when_claims_are_zero(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            run_dir = tmp_dir / "risultati" / "runs" / "test-run-signals"
            document_dir = run_dir / "document_analysis"
            document_dir.mkdir(parents=True)
            (document_dir / "document_quality_assessment.json").write_text(
                json.dumps(
                    {
                        "@type": "DocumentQualityAssessmentSet",
                        "documents": [
                            {
                                "source_document_id": "doc-1",
                                "title": "Documento multi-scheda",
                                "document_class": "text_document",
                                "quality_status": "ready_for_manual_review",
                                "review_status": "unreviewed",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (document_dir / "candidate_document_person_links.json").write_text(
                json.dumps(
                    {
                        "@type": "CandidateDocumentPersonLinkSet",
                        "candidate_document_person_links": [
                            {
                                "@id": "candidate-document-person-link:andreoli-doc-1",
                                "profile_id": "person:purocielo:andreoli-dino",
                                "source_document_id": "doc-1",
                                "score": 0.92,
                                "context": "Andreoli Dino, nato il 17 maggio 1920.",
                                "review_status": "unreviewed",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (document_dir / "extracted_entities.json").write_text(
                json.dumps(
                    {
                        "@type": "ExtractedEntitySet",
                        "extracted_entities": [
                            {
                                "@id": "extracted-entity:birth-date",
                                "entity_type": "date",
                                "value": "17 maggio 1920",
                                "source_document_id": "doc-1",
                                "context": "Andreoli Dino, nato il 17 maggio 1920.",
                                "score": 0.8,
                                "reasons": ["italian_textual_date_pattern"],
                                "review_status": "unreviewed",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (document_dir / "candidate_evidence_claims.json").write_text(
                json.dumps(
                    {
                        "@type": "CandidateEvidenceClaimSet",
                        "claim_count": 0,
                        "skipped_count": 1,
                        "candidate_evidence_claims": [],
                        "skipped_entities": [
                            {
                                "@type": "SkippedCandidateClaim",
                                "@id": "skipped-candidate-claim:birth-date",
                                "source_document_id": "doc-1",
                                "entity_id": "extracted-entity:birth-date",
                                "entity_type": "date",
                                "value": "17 maggio 1920",
                                "context": "Andreoli Dino, nato il 17 maggio 1920.",
                                "reason": "ambiguous_or_missing_document_person_link",
                                "recommended_next_action": "better_segmentation_or_link_review",
                                "candidate_profile_ids": ["person:purocielo:andreoli-dino"],
                                "review_status": "unreviewed",
                                "publication_status": "not_publishable_without_human_review",
                            }
                        ],
                        "skipped_structured_documents": [
                            {
                                "@type": "SkippedStructuredDocumentClaimCandidate",
                                "@id": "skipped-structured-document-claim:doc-1",
                                "source_document_id": "doc-1",
                                "source_id": "partigiani_italia",
                                "title": "Scheda strutturata Andreoli",
                                "url": "https://example.test/andreoli",
                                "reason": "missing_source_detail_claim_mappings",
                                "recommended_next_action": "manual_review",
                                "candidate_profile_ids": ["person:purocielo:andreoli-dino"],
                                "candidate_document_person_link_ids": ["candidate-document-person-link:andreoli-doc-1"],
                                "review_status": "unreviewed",
                                "publication_status": "not_publishable_without_human_review",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (document_dir / "research_feedback_actions.json").write_text(
                json.dumps(
                    {
                        "@type": "ResearchFeedbackActionSet",
                        "documents": [
                            {
                                "source_document_id": "doc-1",
                                "actions": [
                                    {
                                        "@id": "research-feedback-action:andreoli-doc-1",
                                        "value": "Andreoli Dino",
                                        "source_document_id": "doc-1",
                                        "context": {"quote": "Andreoli Dino, nato il 17 maggio 1920."},
                                        "reasons": ["person_mention_with_date"],
                                        "review_status": "unreviewed",
                                    }
                                ],
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = build_mvp_pilot_summary(
                run_dir=run_dir,
                profiles_index=profiles_index,
                output_md=document_dir / "mvp_pilot_summary.md",
            )
            markdown = (document_dir / "mvp_pilot_summary.md").read_text(encoding="utf-8")

        self.assertEqual(summary["candidate_evidence_claim_count"], 0)
        self.assertGreater(summary["reviewable_document_signal_count"], 0)
        claim_funnel = summary["mvp_signal_diagnostics"]["claim_funnel_diagnostics"]
        self.assertEqual(claim_funnel["@type"], "MvpClaimFunnelDiagnostics")
        self.assertEqual(claim_funnel["funnel_status"], "blocked_with_reviewable_skips")
        self.assertEqual(claim_funnel["skipped_entity_count"], 1)
        self.assertEqual(claim_funnel["skipped_with_candidate_profiles_count"], 1)
        self.assertEqual(claim_funnel["counts_by_skip_reason"]["ambiguous_or_missing_document_person_link"], 1)
        self.assertEqual(
            summary["mvp_signal_diagnostics"]["claim_funnel_next_action"],
            "Rafforzare segmentazione o link documento-persona sui casi ambigui.",
        )
        self.assertEqual(summary["profile_readiness"][0]["readiness_status"], "needs_signal_review")
        self.assertEqual(summary["pilot_package_scorecard"]["package_status"], "needs_document_signal_review")
        self.assertIn("ambiguous_or_missing_document_person_link", json.dumps(summary))
        signal_groups = summary["reviewable_document_signals"]
        skipped_signals = [
            signal
            for group in signal_groups
            for signal in group["signals"]
            if signal["signal_type"] == "skipped_claim_candidate"
        ]
        self.assertEqual(len(skipped_signals), 1)
        self.assertEqual(skipped_signals[0]["value"], "17 maggio 1920")
        self.assertEqual(skipped_signals[0]["recommended_next_action"], "better_segmentation_or_link_review")
        self.assertEqual(skipped_signals[0]["publication_status"], "not_publishable_without_human_review")
        structured_skips = [
            signal
            for group in signal_groups
            for signal in group["signals"]
            if signal["signal_type"] == "skipped_structured_document_claim_candidate"
        ]
        self.assertEqual(len(structured_skips), 1)
        self.assertEqual(structured_skips[0]["value"], "missing_source_detail_claim_mappings")
        self.assertEqual(structured_skips[0]["recommended_next_action"], "manual_review")
        self.assertIn("Scheda strutturata Andreoli", structured_skips[0]["context"])
        self.assertIn("Piste documentali per profilo", markdown)
        self.assertIn("Funnel claim", markdown)
        self.assertIn("Motivi skip claim", markdown)
        self.assertIn("Andreoli Dino, nato il 17 maggio 1920", markdown)
        self.assertNotIn("verified_facts", json.dumps(summary))

    def test_mvp_summary_normalizes_comma_joined_profile_ids(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            profiles_dir = profiles_index.parent
            second_profile = json.loads((profiles_dir / "purocielo-andreoli-dino.jsonld").read_text(encoding="utf-8"))
            second_profile["@id"] = "person:purocielo:guazzaloca-laura"
            second_profile["profile_id"] = "person:purocielo:guazzaloca-laura"
            second_profile["identity"]["canonical_name"] = "Guazzaloca Laura"
            second_profile["identity"]["given_name"] = "Laura"
            second_profile["identity"]["family_name"] = "Guazzaloca"
            second_profile["identity"]["name_forms"] = ["Guazzaloca Laura"]
            (profiles_dir / "purocielo-guazzaloca-laura.jsonld").write_text(
                json.dumps(second_profile, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            index_payload = json.loads(profiles_index.read_text(encoding="utf-8"))
            index_payload["profiles"].append(
                {
                    "@id": "person:purocielo:guazzaloca-laura",
                    "file": "purocielo-guazzaloca-laura.jsonld",
                    "canonical_name": "Guazzaloca Laura",
                }
            )
            profiles_index.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            run_dir = tmp_dir / "risultati" / "runs" / "test-run-profile-normalization"
            document_dir = run_dir / "document_analysis"
            document_dir.mkdir(parents=True)

            summary = build_mvp_pilot_summary(
                run_dir=run_dir,
                profiles_index=profiles_index,
                profile_ids=['"person:purocielo:andreoli-dino","person:purocielo:guazzaloca-laura"'],
            )

        self.assertEqual(
            summary["pilot_profile_ids"],
            ["person:purocielo:andreoli-dino", "person:purocielo:guazzaloca-laura"],
        )
        self.assertEqual(summary["profile_count"], 2)
        self.assertEqual([profile["profile_id"] for profile in summary["profiles"]], summary["pilot_profile_ids"])
        self.assertNotIn("Alcuni ProfileId pilota non sono stati risolti", " ".join(summary["warnings"]))

    def test_mvp_summary_excludes_legacy_seed_profiles_and_their_links(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_dir = tmp_dir / "profiles"
            profiles_dir.mkdir()
            profile = {
                "@type": "PersonResearchProfile",
                "@id": "person:purocielo:andreoli-dino",
                "profile_id": "person:purocielo:andreoli-dino",
                "identity": {"canonical_name": "Andreoli Dino"},
                "seed": {"source": "ricerche\\caduti_purocielo.csv", "source_id": "ANDREOLI DINO", "payload": {}},
            }
            (profiles_dir / "purocielo-andreoli-dino.jsonld").write_text(
                json.dumps(profile, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            profiles_index = profiles_dir / "purocielo.index.jsonld"
            profiles_index.write_text(
                json.dumps(
                    {
                        "@type": "PersonResearchProfileIndex",
                        "profiles": [
                            {
                                "@id": "person:purocielo:andreoli-dino",
                                "file": "purocielo-andreoli-dino.jsonld",
                                "canonical_name": "Andreoli Dino",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            run_dir = tmp_dir / "risultati" / "runs" / "test-run-legacy-profile"
            document_dir = run_dir / "document_analysis"
            document_dir.mkdir(parents=True)
            (document_dir / "candidate_document_person_links.json").write_text(
                json.dumps(
                    {
                        "candidate_document_person_links": [
                            {
                                "profile_id": "person:purocielo:andreoli-dino",
                                "source_document_id": "doc-legacy",
                                "context": "Andreoli Dino",
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = build_mvp_pilot_summary(
                run_dir=run_dir,
                profiles_index=profiles_index,
                profile_ids=["person:purocielo:andreoli-dino"],
            )

        self.assertEqual(summary["profile_count"], 0)
        self.assertEqual(summary["candidate_document_person_link_count"], 0)
        self.assertIn("Profili esclusi per seed legacy caduti_purocielo.csv", " ".join(summary["warnings"]))

    def test_pipeline_writes_isolated_manifest_and_summary_without_online(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            processed_dir = write_processed_document(tmp_dir)
            profiles_index = write_profile_index(tmp_dir)
            results_dir = tmp_dir / "risultati"

            manifest = run_document_research_pipeline(
                run_id="test-run",
                processed_dir=processed_dir,
                results_dir=results_dir,
                profiles_index=profiles_index,
                sources_yaml=tmp_dir / "missing-sources.yaml",
                skip_online=True,
                similarity_threshold=0.1,
            )

            run_dir = results_dir / "runs" / "test-run"
            manifest_path = run_dir / "manifest.json"
            summary_path = run_dir / "run_summary.md"
            log_path = run_dir / "run.log"
            claims_path = run_dir / "document_analysis" / "candidate_evidence_claims.json"
            feedback_actions_path = run_dir / "document_analysis" / "research_feedback_actions.json"
            feedback_actions_md_path = run_dir / "document_analysis" / "research_feedback_actions.md"
            place_links_path = run_dir / "document_analysis" / "candidate_document_place_links.json"
            place_links_md_path = run_dir / "document_analysis" / "candidate_document_place_links.md"
            feedback_plan_path = run_dir / "document_analysis" / "feedback_search_plan.json"
            feedback_plan_md_path = run_dir / "document_analysis" / "feedback_search_plan.md"
            mvp_summary_path = run_dir / "document_analysis" / "mvp_pilot_summary.json"
            mvp_summary_md_path = run_dir / "document_analysis" / "mvp_pilot_summary.md"
            log_text = log_path.read_text(encoding="utf-8")

            self.assertEqual(manifest["status"], "completed")
            self.assertTrue(manifest_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertIn("RUN START document_research_pipeline", log_text)
            self.assertIn("STEP START document_quality", log_text)
            self.assertIn("STEP PROGRESS document_quality quality metadata start", log_text)
            self.assertIn("STEP PROGRESS document_quality quality metadata done", log_text)
            self.assertIn("STEP END document_quality status=completed", log_text)
            self.assertIn("RUN END document_research_pipeline", log_text)
            self.assertTrue(claims_path.exists())
            self.assertTrue(feedback_actions_path.exists())
            self.assertTrue(feedback_actions_md_path.exists())
            self.assertTrue(place_links_path.exists())
            self.assertTrue(place_links_md_path.exists())
            self.assertTrue(feedback_plan_path.exists())
            self.assertTrue(feedback_plan_md_path.exists())
            self.assertTrue(mvp_summary_path.exists())
            self.assertTrue(mvp_summary_md_path.exists())
            self.assertFalse((results_dir / "document_analysis" / "candidate_evidence_claims.json").exists())
            self.assertFalse((results_dir / "document_analysis" / "research_feedback_actions.json").exists())
            self.assertFalse((results_dir / "document_analysis" / "candidate_document_place_links.json").exists())
            self.assertFalse((results_dir / "document_analysis" / "feedback_search_plan.json").exists())

            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["@type"], "DocumentResearchRunManifest")
            self.assertEqual(persisted["run_id"], "test-run")
            self.assertEqual(persisted["outputs"]["run_log"], str(log_path))
            self.assertTrue(any(step["name"] == "online_profile_search" and step["status"] == "skipped" for step in persisted["steps"]))
            feedback_steps = [step for step in persisted["steps"] if step["name"] == "research_feedback_actions"]
            self.assertEqual(feedback_steps[0]["status"], "completed")
            self.assertEqual(feedback_steps[0]["summary"]["action_count"], 1)
            place_link_steps = [step for step in persisted["steps"] if step["name"] == "candidate_document_place_links"]
            self.assertEqual(place_link_steps[0]["status"], "completed")
            self.assertEqual(place_link_steps[0]["summary"]["link_count"], 1)
            feedback_plan_steps = [step for step in persisted["steps"] if step["name"] == "feedback_search_plan"]
            self.assertEqual(feedback_plan_steps[0]["status"], "completed")
            self.assertEqual(feedback_plan_steps[0]["summary"]["plan_count"], 1)
            mvp_steps = [step for step in persisted["steps"] if step["name"] == "mvp_pilot_summary"]
            self.assertEqual(mvp_steps[0]["status"], "completed")
            self.assertEqual(mvp_steps[0]["summary"]["profile_count"], 1)
            self.assertGreaterEqual(mvp_steps[0]["summary"]["candidate_evidence_claim_count"], 1)
            self.assertEqual(persisted["outputs"]["mvp_pilot_summary_json"], str(mvp_summary_path))

            claims = json.loads(claims_path.read_text(encoding="utf-8"))
            self.assertEqual(claims["@type"], "CandidateEvidenceClaimSet")
            self.assertGreaterEqual(claims["claim_count"], 1)
            self.assertTrue(all(claim["review_status"] == "unreviewed" for claim in claims["candidate_evidence_claims"]))
            self.assertNotIn("verified_facts", json.dumps(claims))
            feedback_actions = json.loads(feedback_actions_path.read_text(encoding="utf-8"))
            self.assertEqual(feedback_actions["@type"], "ResearchFeedbackActionSet")
            self.assertEqual(feedback_actions["action_count"], 1)
            self.assertEqual(feedback_actions["documents"][0]["actions"][0]["review_status"], "unreviewed")
            self.assertNotIn("CandidateEvidenceClaim", json.dumps(feedback_actions))
            self.assertNotIn("EvidenceClaim", json.dumps(feedback_actions))
            self.assertNotIn("ProfilePatch", json.dumps(feedback_actions))
            self.assertNotIn("verified_facts", json.dumps(feedback_actions))
            place_links = json.loads(place_links_path.read_text(encoding="utf-8"))
            self.assertEqual(place_links["@type"], "CandidateDocumentPlaceLinkSet")
            self.assertEqual(place_links["link_count"], 1)
            self.assertEqual(place_links["candidate_document_place_links"][0]["place_id"], "place:camalanca:purocielo")
            self.assertEqual(place_links["candidate_document_place_links"][0]["review_status"], "unreviewed")
            self.assertNotIn("EvidenceClaim", json.dumps(place_links))
            self.assertNotIn("verified_facts", json.dumps(place_links))
            feedback_plan = json.loads(feedback_plan_path.read_text(encoding="utf-8"))
            self.assertEqual(feedback_plan["@type"], "FeedbackSearchPlanSet")
            self.assertEqual(feedback_plan["plan_count"], 1)
            self.assertEqual(feedback_plan["plans"][0]["profile_id"], "person:purocielo:andreoli-dino")
            self.assertEqual(feedback_plan["plans"][0]["profile_resolution"]["status"], "resolved")
            self.assertEqual(feedback_plan["plans"][0]["reason"], "no_registered_sources_planned")
            self.assertFalse(feedback_plan["online_search_started"])
            self.assertNotIn("CandidateEvidenceClaim", json.dumps(feedback_plan))
            self.assertNotIn("EvidenceClaim", json.dumps(feedback_plan))
            self.assertNotIn("ProfilePatch", json.dumps(feedback_plan))
            self.assertNotIn("verified_facts", json.dumps(feedback_plan))
            mvp_summary = json.loads(mvp_summary_path.read_text(encoding="utf-8"))
            mvp_summary_md = mvp_summary_md_path.read_text(encoding="utf-8")
            self.assertEqual(mvp_summary["@type"], "MvpPilotSummary")
            self.assertEqual(mvp_summary["profile_count"], 1)
            self.assertEqual(mvp_summary["candidate_document_person_link_count"], 1)
            self.assertGreaterEqual(mvp_summary["candidate_evidence_claim_count"], 1)
            self.assertEqual(mvp_summary["review_status"], "unreviewed")
            self.assertEqual(mvp_summary["profile_readiness"][0]["profile_id"], "person:purocielo:andreoli-dino")
            self.assertEqual(mvp_summary["profile_readiness"][0]["readiness_status"], "ready_for_review")
            self.assertEqual(mvp_summary["profile_readiness"][0]["review_status"], "unreviewed")
            self.assertEqual(mvp_summary["pilot_package_scorecard"]["package_status"], "ready_with_document_intake_warnings")
            self.assertEqual(mvp_summary["pilot_package_scorecard"]["ready_for_review_profile_count"], 1)
            self.assertIn("Andreoli Dino", mvp_summary_md)
            self.assertIn("Stato schede pilota", mvp_summary_md)
            self.assertIn("Scorecard pacchetto MVP", mvp_summary_md)
            self.assertIn("ready_for_review", mvp_summary_md)
            self.assertIn("preview-only", mvp_summary_md)
            self.assertNotIn("ProfilePatch", json.dumps(mvp_summary))
            self.assertNotIn("verified_facts", json.dumps(mvp_summary))

    def test_pipeline_derives_research_inputs_from_research_dir(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            processed_dir = write_processed_document(tmp_dir)
            research_dir = write_research_dir(tmp_dir)
            results_dir = tmp_dir / "risultati"

            manifest = run_document_research_pipeline(
                run_id="test-run-remote-research",
                processed_dir=processed_dir,
                results_dir=results_dir,
                research_dir=research_dir,
                skip_online=True,
                similarity_threshold=0.1,
            )

            manifest_path = results_dir / "runs" / "test-run-remote-research" / "manifest.json"
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            place_links_path = results_dir / "runs" / "test-run-remote-research" / "document_analysis" / "candidate_document_place_links.json"
            place_links = json.loads(place_links_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(persisted["inputs"]["research_dir"], str(research_dir))
        self.assertEqual(persisted["inputs"]["profiles_index"], str(research_dir / "person_profiles" / "purocielo.index.jsonld"))
        self.assertEqual(persisted["inputs"]["sources_yaml"], str(research_dir / "camalanca_fonti.yaml"))
        self.assertEqual(persisted["inputs"]["places_index"], str(research_dir / "places" / "places.index.jsonld"))
        self.assertEqual(place_links["places_index"], str(research_dir / "places" / "places.index.jsonld"))
        self.assertEqual(place_links["link_count"], 1)

    def test_online_requires_explicit_profile_source_and_limit(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            processed_dir = write_processed_document(tmp_dir)
            profiles_index = write_profile_index(tmp_dir)

            manifest = run_document_research_pipeline(
                run_id="test-run-online-guard",
                processed_dir=processed_dir,
                results_dir=tmp_dir / "risultati",
                profiles_index=profiles_index,
                sources_yaml=tmp_dir / "missing-sources.yaml",
                skip_online=False,
            )

            self.assertEqual(manifest["status"], "failed")
            online_steps = [step for step in manifest["steps"] if step["name"] == "online_profile_search"]
            self.assertEqual(online_steps[0]["reason"], "online_requires_explicit_profile_source_and_limit")

    def test_online_step_passes_search_plan_flags_to_profiles_runner(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            processed_dir = write_processed_document(tmp_dir)
            profiles_index = write_profile_index(tmp_dir)
            results_dir = tmp_dir / "risultati"
            sources_yaml = tmp_dir / "sources.yaml"
            acquire_documents_root = tmp_dir / "documenti_da_processare" / "fonti_online"
            calls: list[dict[str, object]] = []

            def fake_run_profiles_report(**kwargs):
                calls.append(dict(kwargs))
                Path(kwargs["output_json"]).write_text(
                    json.dumps(
                        {
                            "include_search_plan": kwargs["include_search_plan"],
                            "planned_execution_mode": "first_planned_attempt",
                            "planned_attempt_execution_limit": 1,
                            "profiles": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                Path(kwargs["output_md"]).write_text("Audit piano ricerca\n", encoding="utf-8")
                return {
                    "exit_code": 0,
                    "output_json": str(kwargs["output_json"]),
                    "output_md": str(kwargs["output_md"]),
                    "output_dir": str(kwargs["output_dir"]),
                    "profiles_count": 1,
                    "sources_count": 1,
                    "acquired_documents_count": 1,
                    "error": "",
                }

            with patch(
                "caduti_fonti_report.document_analysis.pipeline_runner.run_profiles_report",
                side_effect=fake_run_profiles_report,
            ):
                manifest = run_document_research_pipeline(
                    run_id="test-run-planner-audit",
                    processed_dir=processed_dir,
                    results_dir=results_dir,
                    profiles_index=profiles_index,
                    sources_yaml=sources_yaml,
                    profile_id="person:purocielo:andreoli-dino",
                    source_id="storia_memoria_bo",
                    limit=1,
                    include_search_plan=True,
                    execute_first_planned_attempt=True,
                    acquire_documents_root=acquire_documents_root,
                )

            persisted = json.loads((results_dir / "runs" / "test-run-planner-audit" / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "completed")
        self.assertTrue(persisted["inputs"]["include_search_plan"])
        self.assertTrue(persisted["inputs"]["execute_first_planned_attempt"])
        self.assertEqual(persisted["inputs"]["acquire_documents_root"], str(acquire_documents_root))
        self.assertEqual(calls[0]["profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(calls[0]["source_id"], "storia_memoria_bo")
        self.assertEqual(calls[0]["limit"], 1)
        self.assertTrue(calls[0]["include_search_plan"])
        self.assertTrue(calls[0]["execute_first_planned_attempt"])
        self.assertEqual(calls[0]["acquire_documents_root"], acquire_documents_root)
        online_steps = [step for step in persisted["steps"] if step["name"] == "online_profile_search"]
        self.assertEqual(online_steps[0]["status"], "completed")
        self.assertEqual(online_steps[0]["summary"]["profiles_count"], 1)
        self.assertEqual(online_steps[0]["summary"]["acquired_documents_count"], 1)


if __name__ == "__main__":
    unittest.main()
