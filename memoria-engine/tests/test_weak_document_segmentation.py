from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.weak_document_segmentation import (  # noqa: E402
    render_weak_segments_markdown,
    weak_segment_document_chunks,
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


def write_chunk_payload(
    root_dir: Path,
    *,
    source_id: str = "manual_uploads",
    source_document_id: str = "doc:1",
    text: str,
    text_quality_warnings: list[str] | None = None,
) -> Path:
    chunk_dir = root_dir / source_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    path = chunk_dir / f"{source_document_id.replace(':', '-')}.chunks.json"
    payload = {
        "@type": "PhysicalDocumentChunkDocument",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "document_class": "word_document",
        "review_status": "unreviewed",
        "text_file": f"{source_id}/{source_document_id}.text.json",
        "text_sha256": "sha",
        "chunk_count": 1,
        "chunks": [
            {
                "@type": "PhysicalDocumentChunk",
                "@id": "physical-document-chunk:test",
                "chunk_id": "physical-document-chunk:test",
                "source_id": source_id,
                "source_document_id": source_document_id,
                "chunk_index": 1,
                "char_start": 0,
                "char_end": len(text),
                "text": text,
                "text_quality_warnings": text_quality_warnings or [],
                "review_status": "unreviewed",
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class WeakDocumentSegmentationTests(unittest.TestCase):
    def test_builds_weak_segments_with_provenance_and_no_claims(self) -> None:
        text = (
            "Andreoli Dino risulta citato in una nota locale. "
            "La Brigata Garibaldi opera nella zona. "
            "Riferimento archivistico RH 36/117/3 nel fascicolo."
        )
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            output_dir = tmp_dir / "segments"
            output_json = tmp_dir / "weak_segments.json"
            output_md = tmp_dir / "weak_segments.md"
            write_chunk_payload(chunk_dir, source_document_id="doc:signals", text=text)

            payload = weak_segment_document_chunks(
                chunk_dir=chunk_dir,
                output_dir=output_dir,
                output_json=output_json,
                output_md=output_md,
            )
            document = payload["documents"][0]
            segments = document["segments"]
            persisted = json.loads((output_dir / "manual_uploads" / "doc-signals.weak-segments.json").read_text("utf-8"))
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        segment_types = {segment["segment_type"] for segment in segments}
        self.assertEqual(payload["@type"], "WeakDocumentSegmentSet")
        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["segment_count"], 3)
        self.assertEqual(document["@type"], "WeakDocumentSegmentDocument")
        self.assertEqual(document["review_status"], "unreviewed")
        self.assertEqual(persisted["segment_count"], 3)
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertEqual(
            segment_types,
            {"person_mention_context", "formation_context", "archival_reference_context"},
        )
        self.assertTrue(all(segment["@type"] == "WeakDocumentSegment" for segment in segments))
        self.assertTrue(all(segment["review_status"] == "unreviewed" for segment in segments))
        self.assertTrue(all(segment["claim_extraction_allowed"] is False for segment in segments))
        self.assertTrue(all(segment["chunk_id"] == "physical-document-chunk:test" for segment in segments))
        self.assertTrue(all(segment["text_quality_warnings"] == [] for segment in segments))
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_propagates_encoding_warnings_from_chunks_to_segments_without_changing_text(self) -> None:
        text = "Andreoli Dino a CaÃ¢â‚¬â„¢ di Malanca nella Brigata Garibaldi."
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunk_payload(
                chunk_dir,
                source_document_id="doc:mojibake",
                text=text,
                text_quality_warnings=["encoding_suspect_mojibake"],
            )

            payload = weak_segment_document_chunks(chunk_dir=chunk_dir)

        segments = payload["documents"][0]["segments"]
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["text"], text)
        self.assertEqual(segments[0]["text_quality_warnings"], ["encoding_suspect_mojibake"])
        self.assertIn("encoding_suspect_mojibake", segments[0]["warnings"])
        self.assertFalse(segments[0]["claim_extraction_allowed"])
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_chunks_without_signals_without_promoting_facts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunk_payload(chunk_dir, source_document_id="doc:none", text="testo generico senza segnali utili")

            payload = weak_segment_document_chunks(chunk_dir=chunk_dir)

        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["segment_count"], 0)
        self.assertEqual(payload["documents"][0]["segments"], [])
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_invalid_chunk_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            chunk_dir.mkdir()
            (chunk_dir / "bad.chunks.json").write_text(
                json.dumps({"@type": "ProcessedDocumentText", "source_document_id": "doc:bad"}),
                encoding="utf-8",
            )

            payload = weak_segment_document_chunks(chunk_dir=chunk_dir)

        self.assertEqual(payload["document_count"], 0)
        self.assertEqual(payload["segment_count"], 0)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "unsupported_payload_type")

    def test_markdown_renderer_lists_segments_for_review(self) -> None:
        payload = {
            "segmentation_method": "deterministic_weak_segment_rules",
            "document_count": 1,
            "segment_count": 1,
            "skipped_count": 0,
            "documents": [
                {
                    "source_document_id": "doc:1",
                    "source_id": "manual_uploads",
                    "review_status": "unreviewed",
                    "segment_count": 1,
                    "chunk_file": "doc.chunks.json",
                    "segments": [
                        {
                            "segment_id": "weak-document-segment:abc",
                            "segment_type": "person_mention_context",
                            "chunk_index": 1,
                            "chunk_char_start": 0,
                            "chunk_char_end": 20,
                            "confidence": 0.6,
                        }
                    ],
                }
            ],
        }

        markdown = render_weak_segments_markdown(payload)

        self.assertIn("# WeakDocumentSegment preview", markdown)
        self.assertIn("weak-document-segment:abc", markdown)
        self.assertIn("unreviewed", markdown)
