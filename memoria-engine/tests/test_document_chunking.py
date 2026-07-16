from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.document_chunking import (  # noqa: E402
    chunk_document_texts,
    render_document_chunks_markdown,
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


def write_text_payload(
    root_dir: Path,
    *,
    source_id: str = "manual_uploads",
    source_document_id: str = "doc:1",
    text: str,
    text_status: str = "extracted",
    document_class: str = "word_document",
) -> Path:
    text_dir = root_dir / source_id
    text_dir.mkdir(parents=True, exist_ok=True)
    path = text_dir / f"{source_document_id.replace(':', '-')}.text.json"
    payload = {
        "@type": "ProcessedDocumentText",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "document_class": document_class,
        "claim_eligible": True,
        "review_status": "unreviewed",
        "raw_file": f"{source_id}/{source_document_id}.docx",
        "metadata_file": f"{source_id}/{source_document_id}.metadata.json",
        "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "extraction_status": "text_extracted" if text_status == "extracted" else "manual_ocr_required",
        "text_status": text_status,
        "text": text,
        "text_length": len(text),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class DocumentChunkingTests(unittest.TestCase):
    def test_builds_physical_chunks_with_overlap_and_provenance(self) -> None:
        text = "0123456789" * 26
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            output_dir = tmp_dir / "chunks"
            output_json = tmp_dir / "document_chunks.json"
            output_md = tmp_dir / "document_chunks.md"
            write_text_payload(text_dir, source_document_id="doc:long", text=text)

            payload = chunk_document_texts(
                text_dir=text_dir,
                output_dir=output_dir,
                output_json=output_json,
                output_md=output_md,
                max_chars=100,
                overlap_chars=20,
            )
            document = payload["documents"][0]
            chunks = document["chunks"]
            chunk_file = output_dir / "manual_uploads" / "doc-long.chunks.json"
            persisted = json.loads(chunk_file.read_text(encoding="utf-8"))
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        self.assertEqual(payload["@type"], "PhysicalDocumentChunkSet")
        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["chunk_count"], 3)
        self.assertEqual(document["@type"], "PhysicalDocumentChunkDocument")
        self.assertEqual(document["source_document_id"], "doc:long")
        self.assertEqual(document["review_status"], "unreviewed")
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertEqual(persisted["chunk_count"], 3)
        self.assertEqual(chunks[0]["@type"], "PhysicalDocumentChunk")
        self.assertEqual(chunks[0]["char_start"], 0)
        self.assertEqual(chunks[0]["char_end"], 100)
        self.assertFalse(chunks[0]["overlap_previous"])
        self.assertTrue(chunks[0]["overlap_next"])
        self.assertEqual(chunks[0]["boundary_strategy"], "fixed_window_fallback")
        self.assertFalse(chunks[0]["boundary_adjusted"])
        self.assertEqual(chunks[1]["char_start"], 80)
        self.assertTrue(chunks[1]["overlap_previous"])
        self.assertTrue(all(chunk["review_status"] == "unreviewed" for chunk in chunks))
        self.assertTrue(all(chunk["extraction_method"] == "fixed_window_chunking" for chunk in chunks))
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_short_text_generates_single_chunk(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(text_dir, source_document_id="doc:short", text="Andreoli Dino")

            payload = chunk_document_texts(text_dir=text_dir, max_chars=100, overlap_chars=20)

        chunks = payload["documents"][0]["chunks"]
        self.assertEqual(payload["chunk_count"], 1)
        self.assertEqual(chunks[0]["text"], "Andreoli Dino")
        self.assertFalse(chunks[0]["overlap_previous"])
        self.assertFalse(chunks[0]["overlap_next"])
        self.assertEqual(chunks[0]["boundary_strategy"], "document_end")
        self.assertFalse(chunks[0]["boundary_adjusted"])
        self.assertEqual(chunks[0]["text_quality_warnings"], [])

    def test_prefers_sentence_boundary_near_chunk_limit_without_changing_text(self) -> None:
        text = f"{'A' * 65}. {'B' * 80}"
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(text_dir, source_document_id="doc:boundary", text=text)

            payload = chunk_document_texts(text_dir=text_dir, max_chars=80, overlap_chars=10)

        chunks = payload["documents"][0]["chunks"]
        first_chunk = chunks[0]
        self.assertEqual(first_chunk["char_end"], 67)
        self.assertEqual(first_chunk["text"], text[:67])
        self.assertTrue(first_chunk["text"].endswith(". "))
        self.assertEqual(first_chunk["boundary_strategy"], "sentence_near_limit")
        self.assertTrue(first_chunk["boundary_adjusted"])
        self.assertEqual(first_chunk["boundary_reason"], "sentence_boundary_before_max_chars")
        self.assertEqual(chunks[1]["char_start"], 57)
        self.assertEqual(chunks[-1]["char_end"], len(text))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_marks_mojibake_as_text_quality_warning_without_changing_text(self) -> None:
        text = "CaÃ¢â‚¬â„¢ di Malanca e 36Ã‚Âª Brigata Garibaldi"
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(text_dir, source_document_id="doc:mojibake", text=text)

            payload = chunk_document_texts(text_dir=text_dir, max_chars=100, overlap_chars=20)

        chunk = payload["documents"][0]["chunks"][0]
        self.assertEqual(chunk["text"], text)
        self.assertEqual(chunk["text_quality_warnings"], ["encoding_suspect_mojibake"])
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_not_extracted_and_audit_only_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(text_dir, source_document_id="doc:missing", text="", text_status="not_extracted")
            write_text_payload(
                text_dir,
                source_document_id="doc:result",
                text="Risultato di ricerca per audit",
                document_class="result_page",
            )

            payload = chunk_document_texts(text_dir=text_dir, max_chars=100, overlap_chars=20)

        self.assertEqual(payload["document_count"], 0)
        self.assertEqual(payload["chunk_count"], 0)
        self.assertEqual(payload["skipped_count"], 2)
        self.assertEqual(
            {item["reason"] for item in payload["skipped_documents"]},
            {"text_not_extracted", "skipped_result_page"},
        )

    def test_markdown_renderer_lists_chunks_for_review(self) -> None:
        payload = {
            "chunking_method": "fixed_window_chunking",
            "max_chars": 100,
            "overlap_chars": 20,
            "document_count": 1,
            "chunk_count": 1,
            "skipped_count": 0,
            "documents": [
                {
                    "source_document_id": "doc:1",
                    "source_id": "manual_uploads",
                    "document_class": "word_document",
                    "review_status": "unreviewed",
                    "text_file": "doc.text.json",
                    "chunk_count": 1,
                    "chunks": [
                        {
                            "chunk_id": "physical-document-chunk:abc",
                            "char_start": 0,
                            "char_end": 42,
                            "overlap_previous": False,
                            "overlap_next": False,
                        }
                    ],
                }
            ],
        }

        markdown = render_document_chunks_markdown(payload)

        self.assertIn("# PhysicalDocumentChunk preview", markdown)
        self.assertIn("physical-document-chunk:abc", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
