from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.candidate_claim_diagnostics import (  # noqa: E402
    build_claim_funnel_diagnostics,
)
from caduti_fonti_report.document_analysis.candidate_claim_skips import (  # noqa: E402
    candidate_links_for_skipped_entity,
    skipped_candidate_claim,
    skipped_structured_document,
)
from caduti_fonti_report.document_analysis.candidate_claims import (  # noqa: E402
    build_candidate_document_claims,
    render_candidate_document_claims_markdown,
)
from caduti_fonti_report.document_analysis.document_quality import assess_document_quality  # noqa: E402
from caduti_fonti_report.document_analysis.entity_extraction import extract_document_entities  # noqa: E402
from caduti_fonti_report.document_analysis.manual_registration import register_manual_document  # noqa: E402
from caduti_fonti_report.document_analysis.metadata_extraction import extract_document_metadata  # noqa: E402
from caduti_fonti_report.document_analysis.person_linking import build_candidate_document_person_links  # noqa: E402
from caduti_fonti_report.document_analysis.text_extraction import extract_document_text  # noqa: E402


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


def write_inputs(
    root_dir: Path,
    *,
    source_id: str = "camalanca_html",
    document_class: str = "html_document",
    quality_status: str = "ready_for_manual_review",
    links: list[dict[str, object]] | None = None,
    entities: list[dict[str, object]] | None = None,
    metadata: dict[str, object] | None = None,
) -> tuple[Path, Path, Path]:
    entities_json = root_dir / "extracted_entities.json"
    links_json = root_dir / "candidate_document_person_links.json"
    quality_dir = root_dir / "quality" / "camalanca_html"
    quality_dir.mkdir(parents=True)

    default_entities: list[dict[str, object]] = [
        {
            "@type": "ExtractedEntity",
            "@id": "extracted-entity:birth",
            "entity_type": "date",
            "value": "28 gennaio 1920",
            "normalized_value": "28 gennaio 1920",
            "source_id": source_id,
            "source_document_id": "doc-1",
            "title": "Scheda locale",
            "url": "https://www.camalanca.it/scheda/",
            "archival_reference": "",
            "context": "Nato il 28 gennaio 1920 a Bologna.",
            "score": 0.9,
            "reasons": ["italian_textual_date_pattern"],
            "review_status": "unreviewed",
        },
        {
            "@type": "ExtractedEntity",
            "@id": "extracted-entity:formation",
            "entity_type": "formation",
            "value": "36ma brigata Bianconcini Garibaldi",
            "normalized_value": "36ma brigata bianconcini garibaldi",
            "source_id": source_id,
            "source_document_id": "doc-1",
            "title": "Scheda locale",
            "url": "https://www.camalanca.it/scheda/",
            "archival_reference": "",
            "context": "Opero nella 36ma brigata Bianconcini Garibaldi.",
            "score": 0.8,
            "reasons": ["brigata_pattern"],
            "review_status": "unreviewed",
        },
    ]
    default_links: list[dict[str, object]] = [
        {
            "@type": "CandidateDocumentPersonLink",
            "@id": "candidate-document-person-link:1",
            "profile_id": "person:purocielo:andreoli-dino",
            "profile_source_file": "ricerche/person_profiles/purocielo-andreoli-dino.jsonld",
            "canonical_name": "Andreoli Dino",
            "matched_name": "Andreoli Dino",
            "match_kind": "canonical_name",
            "source_id": source_id,
            "source_document_id": "doc-1",
            "title": "Scheda locale",
            "url": "https://www.camalanca.it/scheda/",
            "archival_reference": "",
            "score": 1.0,
            "reasons": ["exact_canonical_name_match"],
            "review_status": "unreviewed",
        }
    ]
    quality = {
        "@type": "DocumentQualityAssessment",
        "source_id": source_id,
        "source_document_id": "doc-1",
        "title": "Scheda locale",
        "document_class": document_class,
        "quality_status": quality_status,
        "classification": "person_detail_or_html_document",
        "claim_allowed": False,
        "review_status": "unreviewed",
    }
    if metadata is not None:
        metadata_payload = {
            "@type": "ProcessedDocumentMetadata",
            "source_id": source_id,
            "source_document_id": "doc-1",
            "title": "Scheda locale",
            "document_class": document_class,
            "claim_eligible": True,
            "url": "https://www.camalanca.it/scheda/",
            "archival_reference": "",
            "review_status": "unreviewed",
        }
        metadata_payload.update(metadata)
        metadata_path = quality_dir / "doc-1.metadata.json"
        metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        quality["metadata_file"] = str(metadata_path)
    entities_json.write_text(
        json.dumps(
            {"@type": "ExtractedEntitySet", "extracted_entities": default_entities if entities is None else entities},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    links_json.write_text(
        json.dumps(
            {"@type": "CandidateDocumentPersonLinkSet", "candidate_document_person_links": default_links if links is None else links},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (quality_dir / "doc-1.quality.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    return entities_json, links_json, root_dir / "quality"


class DocumentCandidateClaimsTests(unittest.TestCase):
    def test_skipped_claim_helper_preserves_candidate_links_and_status(self) -> None:
        entity = {
            "@id": "extracted-entity:archive",
            "source_document_id": "doc-1",
            "source_id": "camalanca_html",
            "title": "Scheda locale",
            "entity_type": "archival_reference",
            "value": "BArch, RH 20-10/199",
            "normalized_value": "barch, rh 20-10/199",
            "context": "Nota archivistica: BArch, RH 20-10/199.",
            "chunk_id": "physical-document-chunk:doc-1:2",
            "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
        }
        links = [
            {
                "@id": "candidate-document-person-link:andreoli",
                "profile_id": "person:purocielo:andreoli-dino",
                "chunk_id": "physical-document-chunk:doc-1:1",
                "weak_segment_id": "weak-document-segment:doc-1:andreoli",
            },
            {
                "@id": "candidate-document-person-link:guazzaloca",
                "profile_id": "person:purocielo:guazzaloca-laura",
                "chunk_id": "physical-document-chunk:doc-1:2",
                "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
            },
        ]

        selected_links = candidate_links_for_skipped_entity(entity=entity, links=links)
        skipped = skipped_candidate_claim(entity=entity, reason="unsupported_entity_context", links=links)
        structured = skipped_structured_document(
            document_id="doc-1",
            reason="missing_source_detail_claim_mappings",
            quality={
                "source_id": "partigiani_italia",
                "title": "Scheda locale",
                "_quality_file": "quality/doc-1.quality.json",
                "metadata_file": "quality/doc-1.metadata.json",
            },
            metadata={
                "source_id": "partigiani_italia",
                "title": "Scheda locale",
                "url": "https://example.test/detail",
                "detail_assessment": "claim_candidates_extracted",
            },
            links=links,
        )

        self.assertEqual(selected_links, [links[1]])
        self.assertEqual(skipped["@type"], "SkippedCandidateClaim")
        self.assertEqual(skipped["@id"], "skipped-candidate-claim:extracted-entity:archive")
        self.assertEqual(skipped["candidate_profile_ids"], ["person:purocielo:guazzaloca-laura"])
        self.assertEqual(skipped["candidate_document_person_link_ids"], ["candidate-document-person-link:guazzaloca"])
        self.assertEqual(skipped["recommended_next_action"], "manual_review")
        self.assertEqual(skipped["review_status"], "unreviewed")
        self.assertEqual(skipped["publication_status"], "not_publishable_without_human_review")
        self.assertEqual(structured["@type"], "SkippedStructuredDocumentClaimCandidate")
        self.assertEqual(
            structured["candidate_profile_ids"],
            ["person:purocielo:andreoli-dino", "person:purocielo:guazzaloca-laura"],
        )
        self.assertEqual(structured["recommended_next_action"], "manual_review")
        self.assertEqual(structured["review_status"], "unreviewed")
        self.assertEqual(structured["publication_status"], "not_publishable_without_human_review")

    def test_claim_funnel_diagnostics_helper_counts_context_and_actions(self) -> None:
        diagnostics = build_claim_funnel_diagnostics(
            claims=[
                {
                    "weak_segment_id": "weak-document-segment:doc-1:andreoli",
                    "chunk_id": "physical-document-chunk:doc-1:1",
                },
                {
                    "weak_segment_id": "",
                    "chunk_id": "physical-document-chunk:doc-1:2",
                },
            ],
            skipped=[
                {
                    "weak_segment_id": "",
                    "chunk_id": "physical-document-chunk:doc-1:3",
                    "reason": "ambiguous_or_missing_document_person_link",
                    "recommended_next_action": "better_segmentation_or_link_review",
                    "candidate_profile_ids": ["person:purocielo:andreoli-dino"],
                },
                {
                    "weak_segment_id": "",
                    "chunk_id": "",
                    "reason": "quality_not_ready_for_manual_review",
                    "recommended_next_action": "quality_review",
                    "candidate_profile_ids": [],
                },
            ],
            skipped_structured_documents=[
                {"reason": "missing_source_detail_claim_mappings"},
            ],
        )

        self.assertEqual(diagnostics["@type"], "ClaimFunnelDiagnostics")
        self.assertEqual(diagnostics["funnel_status"], "claims_with_reviewable_skips")
        self.assertEqual(diagnostics["claim_count"], 2)
        self.assertEqual(diagnostics["claims_with_weak_segment_id_count"], 1)
        self.assertEqual(diagnostics["claims_with_chunk_id_only_count"], 1)
        self.assertEqual(diagnostics["skipped_with_candidate_profiles_count"], 1)
        self.assertEqual(diagnostics["skipped_without_candidate_profiles_count"], 1)
        self.assertEqual(diagnostics["counts_by_skip_reason"]["ambiguous_or_missing_document_person_link"], 1)
        self.assertEqual(diagnostics["counts_by_structured_skip_reason"]["missing_source_detail_claim_mappings"], 1)
        self.assertEqual(diagnostics["counts_by_recommended_next_action"]["quality_review"], 1)
        self.assertEqual(
            diagnostics["next_action"],
            "Rafforzare segmentazione o link documento-persona sui casi ambigui.",
        )
        self.assertEqual(diagnostics["review_status"], "unreviewed")
        self.assertEqual(diagnostics["publication_status"], "not_publishable_without_human_review")

    def test_builds_preview_claims_without_verified_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            entities_json, links_json, quality_dir = write_inputs(tmp_dir)
            output_json = tmp_dir / "candidate_evidence_claims.json"
            output_md = tmp_dir / "candidate_evidence_claims.md"

            payload = build_candidate_document_claims(
                entities_json=entities_json,
                links_json=links_json,
                quality_dir=quality_dir,
                output_json=output_json,
                output_md=output_md,
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        claims = payload["candidate_evidence_claims"]
        by_field = {claim["field"]: claim for claim in claims}
        self.assertEqual(payload["@type"], "CandidateEvidenceClaimSet")
        self.assertEqual(payload["claim_count"], 2)
        self.assertEqual(by_field["birth.date"]["person_candidate_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(by_field["birth.date"]["value"], "28 gennaio 1920")
        self.assertEqual(by_field["formation.name"]["value"], "36ma brigata Bianconcini Garibaldi")
        self.assertTrue(all(claim["review_status"] == "unreviewed" for claim in claims))
        self.assertTrue(all(claim["@type"] == "CandidateEvidenceClaim" for claim in claims))
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_builds_structured_online_detail_claims_from_sidecar_metadata(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata = {
                "detail_assessment": "claim_candidates_extracted",
                "detail_extracted_fields_json": json.dumps(
                    {
                        "birth_date": "6 maggio 1921",
                        "birth_municipality": "Budrio",
                        "formation_name": "7 brigata Gap Garibaldi",
                        "recognition_status": "Partigiano",
                        "recognition_commission": "Emilia-Romagna",
                        "archive_series": "Schedario partigiani",
                    },
                    ensure_ascii=False,
                ),
            }
            entities_json, links_json, quality_dir = write_inputs(
                tmp_dir,
                source_id="partigiani_italia",
                entities=[],
                metadata=metadata,
            )

            payload = build_candidate_document_claims(entities_json=entities_json, links_json=links_json, quality_dir=quality_dir)

        by_field = {claim["field"]: claim for claim in payload["candidate_evidence_claims"]}
        self.assertEqual(payload["claim_count"], 6)
        self.assertEqual(by_field["birth.date"]["value"], "6 maggio 1921")
        self.assertEqual(by_field["birth.municipality"]["value"], "Budrio")
        self.assertEqual(by_field["formation.name"]["value"], "7 brigata Gap Garibaldi")
        self.assertEqual(by_field["partisan.recognition_status"]["value"], "Partigiano")
        self.assertEqual(by_field["archive.recognition_commission"]["value"], "Emilia-Romagna")
        self.assertEqual(by_field["archive.series"]["value"], "Schedario partigiani")
        self.assertTrue(all(claim["extraction_method"] == "online_detail_structured_fields" for claim in by_field.values()))
        self.assertTrue(all(claim["review_status"] == "unreviewed" for claim in by_field.values()))
        self.assertIn("detail_extracted_fields_json", by_field["birth.date"]["reasons"])
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_structured_online_detail_claims_without_unambiguous_person_link(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata = {
                "detail_assessment": "claim_candidates_extracted",
                "detail_extracted_fields_json": json.dumps({"birth_date": "6 maggio 1921"}, ensure_ascii=False),
            }
            links = [
                {"profile_id": "person:purocielo:andreoli-dino", "source_id": "partigiani_italia", "source_document_id": "doc-1", "score": 0.9},
                {"profile_id": "person:purocielo:balboni-william", "source_id": "partigiani_italia", "source_document_id": "doc-1", "score": 0.9},
            ]
            entities_json, links_json, quality_dir = write_inputs(
                tmp_dir,
                source_id="partigiani_italia",
                entities=[],
                links=links,
                metadata=metadata,
            )

            payload = build_candidate_document_claims(entities_json=entities_json, links_json=links_json, quality_dir=quality_dir)

        self.assertEqual(payload["claim_count"], 0)
        self.assertIn(
            "ambiguous_or_missing_document_person_link",
            {item["reason"] for item in payload["skipped_structured_documents"]},
        )
        skipped = payload["skipped_structured_documents"][0]
        self.assertEqual(skipped["@type"], "SkippedStructuredDocumentClaimCandidate")
        self.assertEqual(
            skipped["candidate_profile_ids"],
            ["person:purocielo:andreoli-dino", "person:purocielo:balboni-william"],
        )
        self.assertEqual(skipped["recommended_next_action"], "better_segmentation_or_link_review")
        self.assertEqual(skipped["review_status"], "unreviewed")
        self.assertEqual(skipped["publication_status"], "not_publishable_without_human_review")
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(skipped))

    def test_structured_online_claim_preferred_over_generic_text_claim_duplicate(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata = {
                "detail_assessment": "claim_candidates_extracted",
                "detail_extracted_fields_json": json.dumps({"formation_name": "36ma brigata Bianconcini Garibaldi"}, ensure_ascii=False),
            }
            entities = [
                {
                    "@type": "ExtractedEntity",
                    "@id": "extracted-entity:formation",
                    "entity_type": "formation",
                    "value": "36ma brigata Bianconcini Garibaldi",
                    "normalized_value": "36ma brigata bianconcini garibaldi",
                    "source_id": "partigiani_italia",
                    "source_document_id": "doc-1",
                    "context": "Formazione: 36ma brigata Bianconcini Garibaldi.",
                    "score": 0.8,
                    "reasons": ["brigata_pattern"],
                    "review_status": "unreviewed",
                }
            ]
            entities_json, links_json, quality_dir = write_inputs(
                tmp_dir,
                source_id="partigiani_italia",
                entities=entities,
                metadata=metadata,
            )

            payload = build_candidate_document_claims(entities_json=entities_json, links_json=links_json, quality_dir=quality_dir)

        self.assertEqual(payload["claim_count"], 1)
        claim = payload["candidate_evidence_claims"][0]
        self.assertEqual(claim["field"], "formation.name")
        self.assertEqual(claim["extraction_method"], "online_detail_structured_fields")

    def test_builds_death_date_only_from_explicit_context(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            entities = [
                {
                    "@id": "extracted-entity:death",
                    "entity_type": "date",
                    "value": "12 ottobre 1944",
                    "normalized_value": "12 ottobre 1944",
                    "source_id": "camalanca_html",
                    "source_document_id": "doc-1",
                    "context": "Caduto il 12 ottobre 1944.",
                    "score": 0.9,
                    "reasons": ["italian_textual_date_pattern"],
                    "review_status": "unreviewed",
                }
            ]
            entities_json, links_json, quality_dir = write_inputs(tmp_dir, entities=entities)

            payload = build_candidate_document_claims(entities_json=entities_json, links_json=links_json, quality_dir=quality_dir)

        self.assertEqual(payload["claim_count"], 1)
        self.assertEqual(payload["candidate_evidence_claims"][0]["field"], "death.date")

    def test_segment_scoped_link_resolves_multi_person_document_claim(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            entities = [
                {
                    "@type": "ExtractedEntity",
                    "@id": "extracted-entity:guazzaloca-birth",
                    "entity_type": "date",
                    "value": "28 gennaio 1920",
                    "normalized_value": "28 gennaio 1920",
                    "source_id": "camalanca_html",
                    "source_document_id": "doc-1",
                    "context": "Guazzaloca Laura, nata il 28 gennaio 1920 a Bologna.",
                    "chunk_id": "physical-document-chunk:doc-1:2",
                    "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
                    "score": 0.9,
                    "reasons": ["segment_mention_entity"],
                    "review_status": "unreviewed",
                }
            ]
            links = [
                {
                    "@type": "CandidateDocumentPersonLink",
                    "@id": "candidate-document-person-link:andreoli",
                    "profile_id": "person:purocielo:andreoli-dino",
                    "profile_source_file": "ricerche/person_profiles/purocielo-andreoli-dino.jsonld",
                    "source_id": "camalanca_html",
                    "source_document_id": "doc-1",
                    "score": 0.8,
                    "chunk_id": "physical-document-chunk:doc-1:1",
                    "weak_segment_id": "weak-document-segment:doc-1:andreoli",
                    "review_status": "unreviewed",
                },
                {
                    "@type": "CandidateDocumentPersonLink",
                    "@id": "candidate-document-person-link:guazzaloca",
                    "profile_id": "person:purocielo:guazzaloca-laura",
                    "profile_source_file": "ricerche/person_profiles/purocielo-guazzaloca-laura.jsonld",
                    "source_id": "camalanca_html",
                    "source_document_id": "doc-1",
                    "score": 0.82,
                    "chunk_id": "physical-document-chunk:doc-1:2",
                    "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
                    "review_status": "unreviewed",
                },
            ]
            entities_json, links_json, quality_dir = write_inputs(tmp_dir, entities=entities, links=links)

            payload = build_candidate_document_claims(entities_json=entities_json, links_json=links_json, quality_dir=quality_dir)

        self.assertEqual(payload["claim_count"], 1)
        claim = payload["candidate_evidence_claims"][0]
        self.assertEqual(claim["profile_id"], "person:purocielo:guazzaloca-laura")
        self.assertEqual(claim["weak_segment_id"], "weak-document-segment:doc-1:guazzaloca")
        self.assertIn("segment_scoped_document_person_link", claim["reasons"])
        self.assertNotIn("ambiguous_or_missing_document_person_link", {item["reason"] for item in payload["skipped_entities"]})

    def test_claim_funnel_diagnostics_counts_claims_and_reviewable_skips(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            entities = [
                {
                    "@type": "ExtractedEntity",
                    "@id": "extracted-entity:birth",
                    "entity_type": "date",
                    "value": "28 gennaio 1920",
                    "normalized_value": "28 gennaio 1920",
                    "source_id": "camalanca_html",
                    "source_document_id": "doc-1",
                    "context": "Guazzaloca Laura, nata il 28 gennaio 1920 a Bologna.",
                    "chunk_id": "physical-document-chunk:doc-1:2",
                    "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
                    "score": 0.9,
                    "reasons": ["segment_mention_entity"],
                    "review_status": "unreviewed",
                },
                {
                    "@type": "ExtractedEntity",
                    "@id": "extracted-entity:archive",
                    "entity_type": "archival_reference",
                    "value": "BArch, RH 20-10/199",
                    "normalized_value": "barch, rh 20-10/199",
                    "source_id": "camalanca_html",
                    "source_document_id": "doc-1",
                    "context": "Nota archivistica: BArch, RH 20-10/199.",
                    "chunk_id": "physical-document-chunk:doc-1:2",
                    "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
                    "score": 0.8,
                    "reasons": ["bundesarchiv_rh_reference_pattern"],
                    "review_status": "unreviewed",
                },
            ]
            links = [
                {
                    "@type": "CandidateDocumentPersonLink",
                    "@id": "candidate-document-person-link:guazzaloca",
                    "profile_id": "person:purocielo:guazzaloca-laura",
                    "profile_source_file": "ricerche/person_profiles/purocielo-guazzaloca-laura.jsonld",
                    "source_id": "camalanca_html",
                    "source_document_id": "doc-1",
                    "score": 0.82,
                    "chunk_id": "physical-document-chunk:doc-1:2",
                    "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
                    "review_status": "unreviewed",
                },
            ]
            entities_json, links_json, quality_dir = write_inputs(tmp_dir, entities=entities, links=links)
            output_md = tmp_dir / "candidate_evidence_claims.md"

            payload = build_candidate_document_claims(
                entities_json=entities_json,
                links_json=links_json,
                quality_dir=quality_dir,
                output_md=output_md,
            )
            markdown = output_md.read_text(encoding="utf-8")

        diagnostics = payload["claim_funnel_diagnostics"]
        self.assertEqual(diagnostics["@type"], "ClaimFunnelDiagnostics")
        self.assertEqual(diagnostics["funnel_status"], "claims_with_reviewable_skips")
        self.assertEqual(diagnostics["claim_count"], 1)
        self.assertEqual(diagnostics["skipped_entity_count"], 1)
        self.assertEqual(diagnostics["claims_with_weak_segment_id_count"], 1)
        self.assertEqual(diagnostics["skipped_with_candidate_profiles_count"], 1)
        self.assertEqual(diagnostics["counts_by_skip_reason"]["unsupported_entity_context"], 1)
        self.assertEqual(diagnostics["counts_by_recommended_next_action"]["manual_review"], 1)
        self.assertIn("Diagnostica funnel claim", markdown)
        self.assertIn("unsupported_entity_context", markdown)
        self.assertNotIn("verified_facts", json.dumps(payload))
        self.assertNotIn("ProfilePatch", json.dumps(payload))

    def test_docx_document_flows_to_candidate_claims_without_verified_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "results"
            profiles_index = write_profile_index(tmp_dir)
            docx_path = raw_dir / "manual_uploads" / "scheda-andreoli.docx"
            _write_minimal_docx(
                docx_path,
                [
                    "Andreoli Dino, nato il 17 maggio 1920 a San Lazzaro di Savena.",
                    "Milito nella 36a brigata Garibaldi.",
                    "Cadde in combattimento il 13 ottobre 1944.",
                ],
            )
            raw_before = docx_path.read_bytes()
            register_manual_document(
                file_path=docx_path,
                source_id="manual_uploads",
                title="Scheda Andreoli DOCX",
                archival_reference="Import manuale DOCX",
                access_date="2026-05-17",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=processed_dir)
            extract_document_text(metadata_dir=processed_dir, output_dir=processed_dir, raw_root_dir=raw_dir)
            assess_document_quality(metadata_dir=processed_dir, text_dir=processed_dir, output_dir=processed_dir)
            links_payload = build_candidate_document_person_links(
                text_dir=processed_dir,
                metadata_dir=processed_dir,
                profiles_index=profiles_index,
                output_json=results_dir / "candidate_document_person_links.json",
            )
            entity_payload = extract_document_entities(
                text_dir=processed_dir,
                metadata_dir=processed_dir,
                output_json=results_dir / "extracted_entities.json",
            )

            claims_payload = build_candidate_document_claims(
                entities_json=results_dir / "extracted_entities.json",
                links_json=results_dir / "candidate_document_person_links.json",
                quality_dir=processed_dir,
            )
            raw_after = docx_path.read_bytes()

        claims = claims_payload["candidate_evidence_claims"]
        by_field = {claim["field"]: claim for claim in claims}
        self.assertEqual(raw_after, raw_before)
        self.assertEqual(links_payload["link_count"], 1)
        self.assertGreaterEqual(entity_payload["entity_count"], 3)
        self.assertEqual(claims_payload["claim_count"], 3)
        self.assertEqual(by_field["birth.date"]["value"], "17 maggio 1920")
        self.assertEqual(by_field["death.date"]["value"], "13 ottobre 1944")
        self.assertEqual(by_field["formation.name"]["value"], "36a brigata Garibaldi")
        self.assertTrue(all(claim["profile_id"] == "person:purocielo:andreoli-dino" for claim in claims))
        self.assertTrue(all(claim["review_status"] == "unreviewed" for claim in claims))
        self.assertTrue(all(claim["@type"] == "CandidateEvidenceClaim" for claim in claims))
        self.assertNotIn('"@type": "EvidenceClaim"', json.dumps(claims_payload))
        self.assertNotIn("verified_facts", json.dumps(claims_payload))

    def test_archival_reference_entities_do_not_become_candidate_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            entities = [
                {
                    "@id": "extracted-entity:rh-reference",
                    "entity_type": "archival_reference",
                    "value": "BArch, RH 20-10/199",
                    "normalized_value": "barch, rh 20-10/199",
                    "source_id": "camalanca_html",
                    "source_document_id": "doc-1",
                    "context": "Nota archivistica: BArch, RH 20-10/199.",
                    "score": 0.82,
                    "reasons": ["bundesarchiv_rh_reference_pattern"],
                    "review_status": "unreviewed",
                }
            ]
            entities_json, links_json, quality_dir = write_inputs(tmp_dir, entities=entities)

            payload = build_candidate_document_claims(entities_json=entities_json, links_json=links_json, quality_dir=quality_dir)

        self.assertEqual(payload["claim_count"], 0)
        skipped = payload["skipped_entities"][0]
        self.assertEqual(skipped["@type"], "SkippedCandidateClaim")
        self.assertEqual(skipped["reason"], "unsupported_entity_context")
        self.assertEqual(skipped["entity_id"], "extracted-entity:rh-reference")
        self.assertEqual(skipped["entity_type"], "archival_reference")
        self.assertEqual(skipped["value"], "BArch, RH 20-10/199")
        self.assertEqual(skipped["context"], "Nota archivistica: BArch, RH 20-10/199.")
        self.assertEqual(skipped["recommended_next_action"], "manual_review")
        self.assertEqual(skipped["review_status"], "unreviewed")
        self.assertEqual(skipped["publication_status"], "not_publishable_without_human_review")
        self.assertNotIn('"@type": "CandidateEvidenceClaim"', json.dumps(skipped))

    def test_skips_result_pages_and_ambiguous_person_links(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            links = [
                {
                    "profile_id": "person:purocielo:andreoli-dino",
                    "source_document_id": "doc-1",
                    "score": 1.0,
                },
                {
                    "profile_id": "person:purocielo:bagni-alfonso",
                    "source_document_id": "doc-1",
                    "score": 1.0,
                },
            ]
            entities_json, links_json, quality_dir = write_inputs(tmp_dir, document_class="result_page", links=links)

            payload = build_candidate_document_claims(entities_json=entities_json, links_json=links_json, quality_dir=quality_dir)

        self.assertEqual(payload["claim_count"], 0)
        skipped = payload["skipped_entities"][0]
        self.assertEqual(skipped["reason"], "skipped_result_page")
        self.assertEqual(
            skipped["candidate_profile_ids"],
            ["person:purocielo:andreoli-dino", "person:purocielo:bagni-alfonso"],
        )
        self.assertEqual(skipped["recommended_next_action"], "quality_review")

    def test_markdown_renderer_lists_claims_for_review(self) -> None:
        payload = {
            "claim_count": 1,
            "skipped_count": 0,
            "candidate_evidence_claims": [
                {
                    "field": "birth.date",
                    "value": "28 gennaio 1920",
                    "profile_id": "person:purocielo:andreoli-dino",
                    "source_document_id": "doc-1",
                    "source_id": "camalanca_html",
                    "review_status": "unreviewed",
                    "confidence": 0.85,
                    "reasons": ["italian_textual_date_pattern"],
                    "evidence_span": "Nato il 28 gennaio 1920.",
                }
            ],
        }

        markdown = render_candidate_document_claims_markdown(payload)

        self.assertIn("# CandidateEvidenceClaim preview", markdown)
        self.assertIn("birth.date", markdown)
        self.assertIn("unreviewed", markdown)


def write_profile_index(root_dir: Path) -> Path:
    profiles_dir = root_dir / "profiles"
    profiles_dir.mkdir()
    profile_file = profiles_dir / "purocielo-andreoli-dino.jsonld"
    profile = {
        "@type": "PersonResearchProfile",
        "@id": "person:purocielo:andreoli-dino",
        "profile_id": "person:purocielo:andreoli-dino",
        "identity": {
            "canonical_name": "Andreoli Dino",
            "given_name": "Dino",
            "family_name": "Andreoli",
            "aliases": [],
            "name_forms": ["Andreoli Dino", "Dino Andreoli"],
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
    profile_file.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    index = {
        "@type": "ca:PersonResearchProfileIndex",
        "profiles": [{"@id": profile["@id"], "file": profile_file.name, "canonical_name": "Andreoli Dino"}],
    }
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def _write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>" for paragraph in paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


if __name__ == "__main__":
    unittest.main()
