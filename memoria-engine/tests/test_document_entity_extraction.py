from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.entity_extraction import (  # noqa: E402
    extract_document_entities,
    render_extracted_entities_markdown,
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


def write_processed_document(
    root_dir: Path,
    *,
    source_id: str = "camalanca_html",
    source_document_id: str = "doc-1",
    document_class: str = "html_document",
    text_status: str = "extracted",
    claim_eligible: bool = True,
    transcription_method: str = "",
    text: str,
) -> tuple[Path, Path]:
    metadata_dir = root_dir / "metadata"
    text_dir = root_dir / "text"
    (metadata_dir / source_id).mkdir(parents=True)
    (text_dir / source_id).mkdir(parents=True)
    metadata_path = metadata_dir / source_id / f"{source_document_id}.metadata.json"
    text_path = text_dir / source_id / f"{source_document_id}.text.json"
    metadata = {
        "@type": "ProcessedDocumentMetadata",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "title": "Scheda locale",
        "document_class": document_class,
        "claim_eligible": claim_eligible,
        "review_status": "unreviewed",
        "raw_file": "raw/document.html",
        "media_type": "text/html",
        "url": "https://www.camalanca.it/scheda/",
        "archival_reference": "",
    }
    text_payload = {
        "@type": "ProcessedDocumentText",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "document_class": document_class,
        "claim_eligible": claim_eligible,
        "review_status": "unreviewed",
        "metadata_file": str(metadata_path),
        "text_status": text_status,
        "extraction_status": "text_extracted" if text_status == "extracted" else "skipped",
        "text": text,
        "text_length": len(text),
    }
    if transcription_method:
        text_payload["transcription_method"] = transcription_method
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    text_path.write_text(json.dumps(text_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_dir, text_dir


class DocumentEntityExtractionTests(unittest.TestCase):
    def test_extracts_reviewable_entities_without_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text=(
                    "Nato il 28 gennaio 1920. Opero nella 36ma brigata Bianconcini Garibaldi. "
                    "Documento collegato a WO 417/92/123."
                ),
            )
            output_json = tmp_dir / "extracted_entities.json"
            output_md = tmp_dir / "extracted_entities.md"

            payload = extract_document_entities(
                text_dir=text_dir,
                metadata_dir=metadata_dir,
                output_json=output_json,
                output_md=output_md,
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

            entities = payload["extracted_entities"]
            by_type = {entity["entity_type"]: entity for entity in entities}
            self.assertEqual(payload["@type"], "ExtractedEntitySet")
            self.assertEqual(payload["entity_count"], 3)
            self.assertEqual(by_type["date"]["value"], "28 gennaio 1920")
            self.assertEqual(by_type["formation"]["value"], "36ma brigata Bianconcini Garibaldi")
            self.assertEqual(by_type["archival_reference"]["value"], "WO 417/92/123")
            self.assertTrue(all(entity["review_status"] == "unreviewed" for entity in entities))
            self.assertTrue(all(entity["source_document_id"] == "doc-1" for entity in entities))
            self.assertTrue(output_json_exists)
            self.assertTrue(output_md_exists)
            self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
            self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_result_pages_even_when_entities_are_present(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                document_class="result_page",
                claim_eligible=False,
                text="Risultati per 28 gennaio 1920 e 36ma brigata.",
            )

            payload = extract_document_entities(text_dir=text_dir, metadata_dir=metadata_dir)

        self.assertEqual(payload["entity_count"], 0)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "skipped_result_page")

    def test_skips_text_not_marked_as_extracted(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text_status="not_extracted",
                text="28 gennaio 1920",
            )

            payload = extract_document_entities(text_dir=text_dir, metadata_dir=metadata_dir)

        self.assertEqual(payload["entity_count"], 0)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "text_not_extracted")

    def test_extracts_segment_scoped_entities_from_document_mentions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text="Documento multi-scheda con Guazzaloca Laura, nata il 28 gennaio 1920.",
            )
            mentions_path = text_dir / "camalanca_html" / "doc-1.mentions.json"
            mentions_path.write_text(
                json.dumps(
                    {
                        "@type": "DocumentMentionCandidateDocument",
                        "source_id": "camalanca_html",
                        "source_document_id": "doc-1",
                        "mentions": [
                            {
                                "@type": "DateMentionCandidate",
                                "@id": "document-mention-candidate:guazzaloca-birth-date",
                                "mention_kind": "date",
                                "value": "28 gennaio 1920",
                                "normalized_value": "28 gennaio 1920",
                                "source_id": "camalanca_html",
                                "source_document_id": "doc-1",
                                "chunk_id": "physical-document-chunk:doc-1:2",
                                "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
                                "context": "Guazzaloca Laura, nata il 28 gennaio 1920.",
                                "confidence": 0.72,
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

            payload = extract_document_entities(text_dir=text_dir, metadata_dir=metadata_dir)

        segment_entities = [
            entity
            for entity in payload["extracted_entities"]
            if entity.get("weak_segment_id") == "weak-document-segment:doc-1:guazzaloca"
        ]
        self.assertEqual(len(segment_entities), 1)
        self.assertEqual(segment_entities[0]["entity_type"], "date")
        self.assertEqual(segment_entities[0]["chunk_id"], "physical-document-chunk:doc-1:2")
        self.assertIn("segment_mention_entity", segment_entities[0]["reasons"])

    def test_formation_extraction_trims_trailing_sentence_words_and_deduplicates_ordinals(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text=(
                    "La 36a Brigata Garibaldi che opero nei dintorni viene citata nel testo. "
                    "La 36ª Brigata Garibaldi compi molte azioni. "
                    "Lo stato maggiore della 36a brigata si riuni per predisporre l'azione."
                ),
            )

            payload = extract_document_entities(text_dir=text_dir, metadata_dir=metadata_dir)

        formations = [entity for entity in payload["extracted_entities"] if entity["entity_type"] == "formation"]
        self.assertEqual(len(formations), 1)
        self.assertEqual(formations[0]["value"], "36a Brigata Garibaldi")
        self.assertEqual(formations[0]["normalized_value"], "36 brigata garibaldi")
        self.assertNotIn("che opero nei", formations[0]["value"])
        self.assertNotIn("si riuni", json.dumps(payload))

    def test_formation_extraction_does_not_cross_sentence_after_brigata(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text="Il comandante della 36a Brigata. Risulta ferito nel combattimento.",
            )

            payload = extract_document_entities(text_dir=text_dir, metadata_dir=metadata_dir)

        formations = [entity for entity in payload["extracted_entities"] if entity["entity_type"] == "formation"]
        self.assertEqual(formations, [])
        self.assertNotIn("Brigata. Risulta", json.dumps(payload))

    def test_formation_extraction_skips_repeated_navigation_and_canonicalizes_bianconcini_order(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text=(
                    "Guzzo Il sentiero di Corbari Storia La Lotta di Liberazione "
                    "I primi nuclei Partigiani La 36a Brigata Garibaldi Bianconcini. "
                    "Milito nella 36a brg. Bianconcini Garibaldi. "
                    "Entrato nella 36a Brigata Garibaldi Bianconcini nel giugno 1944. "
                    "Partecipo alle azioni della 36a Brigata Garibaldi 'Bianconcini'."
                ),
            )

            payload = extract_document_entities(text_dir=text_dir, metadata_dir=metadata_dir)

        formations = [entity for entity in payload["extracted_entities"] if entity["entity_type"] == "formation"]
        self.assertEqual(len(formations), 1)
        self.assertEqual(formations[0]["value"], "36a brg. Bianconcini Garibaldi")
        self.assertEqual(formations[0]["normalized_value"], "36 brigata garibaldi bianconcini")

    def test_extracts_bundesarchiv_rh_references_from_ocr_text_as_unreviewed_entities(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                document_class="image_scan",
                claim_eligible=False,
                transcription_method="external_ocr_unreviewed",
                text=(
                    "OCR esterno non revisionato con nota: BArch, RH 20-10/199, "
                    "Frontaufklaerungstrupp 375. Altro riferimento RH 20-10/173."
                ),
            )

            payload = extract_document_entities(text_dir=text_dir, metadata_dir=metadata_dir)

        references = [entity for entity in payload["extracted_entities"] if entity["entity_type"] == "archival_reference"]
        values = {entity["value"] for entity in references}
        self.assertEqual(payload["entity_count"], 2)
        self.assertEqual(values, {"BArch, RH 20-10/199", "RH 20-10/173"})
        self.assertTrue(all(entity["review_status"] == "unreviewed" for entity in references))
        self.assertTrue(all(entity["reasons"] == ["bundesarchiv_rh_reference_pattern"] for entity in references))
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_markdown_renderer_lists_entities_for_review(self) -> None:
        payload = {
            "entity_count": 1,
            "skipped_count": 0,
            "extracted_entities": [
                {
                    "entity_type": "date",
                    "value": "28 gennaio 1920",
                    "source_document_id": "doc-1",
                    "source_id": "camalanca_html",
                    "title": "Scheda locale",
                    "review_status": "unreviewed",
                    "score": 0.9,
                    "reasons": ["italian_textual_date_pattern"],
                    "context": "Nato il 28 gennaio 1920.",
                }
            ],
        }

        markdown = render_extracted_entities_markdown(payload)

        self.assertIn("# ExtractedEntity preview", markdown)
        self.assertIn("28 gennaio 1920", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
