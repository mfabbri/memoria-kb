from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.document_duplicates import (  # noqa: E402
    find_candidate_duplicate_documents,
    render_candidate_duplicate_documents_markdown,
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


def write_metadata(
    root_dir: Path,
    *,
    source_id: str,
    source_document_id: str,
    sha256: str,
    title: str,
) -> Path:
    metadata_dir = root_dir / source_id
    metadata_dir.mkdir(parents=True, exist_ok=True)
    path = metadata_dir / f"{source_document_id.replace(':', '-')}.metadata.json"
    payload = {
        "@type": "ProcessedDocumentMetadata",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "title": title,
        "document_class": "html_document",
        "claim_eligible": True,
        "review_status": "unreviewed",
        "raw_file": f"{source_id}/{title}",
        "media_type": "text/html",
        "sha256": sha256,
        "url": "https://www.camalanca.it/test/",
        "archival_reference": "",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class DocumentDuplicatesTests(unittest.TestCase):
    def test_builds_exact_duplicate_groups_without_modifying_documents_or_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir = tmp_dir / "metadata"
            duplicate_hash = "abc123def4567890"
            write_metadata(
                metadata_dir,
                source_id="camalanca_html",
                source_document_id="camalanca_html:abc123def4567890",
                sha256=duplicate_hash,
                title="alfonso-bagni.html",
            )
            write_metadata(
                metadata_dir,
                source_id="manual_uploads",
                source_document_id="manual_uploads:abc123def4567890",
                sha256=duplicate_hash,
                title="alfonso-bagni.html",
            )
            write_metadata(
                metadata_dir,
                source_id="manual_uploads",
                source_document_id="manual_uploads:unique",
                sha256="unique-hash",
                title="amato-rossi.html",
            )
            output_json = tmp_dir / "candidate_duplicate_documents.json"
            output_md = tmp_dir / "candidate_duplicate_documents.md"

            payload = find_candidate_duplicate_documents(
                metadata_dir=metadata_dir,
                output_json=output_json,
                output_md=output_md,
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        groups = payload["candidate_duplicate_documents"]
        self.assertEqual(payload["@type"], "CandidateDuplicateDocumentSet")
        self.assertEqual(payload["duplicate_group_count"], 1)
        self.assertEqual(groups[0]["@type"], "CandidateDuplicateDocument")
        self.assertEqual(groups[0]["match_type"], "exact_sha256")
        self.assertEqual(groups[0]["document_count"], 2)
        self.assertEqual(groups[0]["review_status"], "unreviewed")
        self.assertEqual(groups[0]["confidence"], 1.0)
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_documents_without_hash_for_audit(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            metadata_dir = tmp_dir / "metadata"
            write_metadata(
                metadata_dir,
                source_id="manual_uploads",
                source_document_id="manual_uploads:nohash",
                sha256="",
                title="documento.html",
            )

            payload = find_candidate_duplicate_documents(metadata_dir=metadata_dir)

        self.assertEqual(payload["duplicate_group_count"], 0)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "sha256_missing")

    def test_markdown_renderer_lists_duplicate_groups_for_review(self) -> None:
        payload = {
            "duplicate_group_count": 1,
            "skipped_count": 0,
            "candidate_duplicate_documents": [
                {
                    "duplicate_group_id": "candidate-duplicate-document:abc",
                    "match_type": "exact_sha256",
                    "sha256": "abc123",
                    "document_count": 2,
                    "review_status": "unreviewed",
                    "confidence": 1.0,
                    "documents": [
                        {
                            "source_document_id": "doc:1",
                            "source_id": "source_a",
                            "title": "documento.html",
                        }
                    ],
                }
            ],
        }

        markdown = render_candidate_duplicate_documents_markdown(payload)

        self.assertIn("# CandidateDuplicateDocument preview", markdown)
        self.assertIn("candidate-duplicate-document:abc", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
