from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.document_clusters import (  # noqa: E402
    find_document_clusters,
    render_document_clusters_markdown,
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
    source_id: str,
    source_document_id: str,
    text: str,
    text_status: str = "extracted",
) -> Path:
    text_dir = root_dir / source_id
    text_dir.mkdir(parents=True, exist_ok=True)
    path = text_dir / f"{source_document_id.replace(':', '-')}.text.json"
    payload = {
        "@type": "ProcessedDocumentText",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "document_class": "html_document",
        "claim_eligible": True,
        "review_status": "unreviewed",
        "raw_file": f"{source_id}/{source_document_id}.html",
        "metadata_file": f"{source_id}/{source_document_id}.metadata.json",
        "media_type": "text/html",
        "extraction_status": "text_extracted",
        "text_status": text_status,
        "text": text,
        "text_length": len(text),
        "text_sha256": "fixture",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def repeated_text(*parts: str) -> str:
    return " ".join(parts * 45)


class DocumentClustersTests(unittest.TestCase):
    def test_builds_preview_only_clusters_for_similar_processed_texts(self) -> None:
        base_text = repeated_text(
            "resistenza",
            "brigata",
            "purocielo",
            "documento",
            "testimonianza",
            "partigiano",
            "archivio",
            "rastrellamento",
        )
        variant_text = base_text + " nota finale revisione archivistica"
        unrelated_text = repeated_text(
            "ospedale",
            "registro",
            "anagrafe",
            "comune",
            "famiglia",
            "residenza",
            "certificato",
            "nascita",
        )
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(text_dir, source_id="source_a", source_document_id="doc:1", text=base_text)
            write_text_payload(text_dir, source_id="source_b", source_document_id="doc:2", text=variant_text)
            write_text_payload(text_dir, source_id="source_c", source_document_id="doc:3", text=unrelated_text)
            output_json = tmp_dir / "document_clusters.json"
            output_md = tmp_dir / "document_clusters.md"

            payload = find_document_clusters(
                text_dir=text_dir,
                output_json=output_json,
                output_md=output_md,
                similarity_threshold=0.86,
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        clusters = payload["document_clusters"]
        self.assertEqual(payload["@type"], "DocumentClusterSet")
        self.assertEqual(payload["cluster_count"], 1)
        self.assertEqual(clusters[0]["@type"], "DocumentCluster")
        self.assertEqual(clusters[0]["document_count"], 2)
        self.assertEqual(clusters[0]["review_status"], "unreviewed")
        self.assertGreaterEqual(clusters[0]["average_similarity"], 0.86)
        self.assertEqual(
            {document["source_document_id"] for document in clusters[0]["documents"]},
            {"doc:1", "doc:2"},
        )
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_short_or_not_extracted_texts_for_audit(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            text_dir = tmp_dir / "texts"
            write_text_payload(text_dir, source_id="manual", source_document_id="doc:short", text="troppo breve")
            write_text_payload(
                text_dir,
                source_id="manual",
                source_document_id="doc:missing",
                text="",
                text_status="not_extracted",
            )

            payload = find_document_clusters(text_dir=text_dir)

        self.assertEqual(payload["cluster_count"], 0)
        self.assertEqual(payload["skipped_count"], 2)
        self.assertEqual(
            {item["reason"] for item in payload["skipped_documents"]},
            {"text_too_short", "text_not_extracted"},
        )

    def test_markdown_renderer_lists_clusters_for_review(self) -> None:
        payload = {
            "similarity_method": "tfidf_cosine_pure_python",
            "similarity_threshold": 0.86,
            "document_count": 2,
            "cluster_count": 1,
            "skipped_count": 0,
            "document_clusters": [
                {
                    "cluster_id": "document-cluster:abc",
                    "document_count": 2,
                    "average_similarity": 0.91,
                    "min_similarity": 0.9,
                    "max_similarity": 0.92,
                    "review_status": "unreviewed",
                    "documents": [
                        {
                            "source_document_id": "doc:1",
                            "source_id": "source_a",
                            "document_class": "html_document",
                        }
                    ],
                }
            ],
        }

        markdown = render_document_clusters_markdown(payload)

        self.assertIn("# DocumentCluster preview", markdown)
        self.assertIn("document-cluster:abc", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
