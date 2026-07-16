from __future__ import annotations

import hashlib
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.html_registration import register_html_documents
from caduti_fonti_report.document_analysis.inventory import build_raw_document_inventory
from caduti_fonti_report.document_analysis.metadata_extraction import extract_document_metadata
from caduti_fonti_report.document_analysis.text_extraction import extract_document_text


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


class HtmlDocumentRegistrationTests(unittest.TestCase):
    def test_registers_multiple_html_files_without_modifying_originals(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw" / "www.camalanca.it"
            root_dir.mkdir(parents=True)
            first = root_dir / "ancilla-cavina.html"
            second = root_dir / "adelmo-brini.html"
            first.write_text("<html><head><title>Ancilla Cavina</title></head><body>Testo A</body></html>", encoding="utf-8")
            second.write_text("<html><body>Testo B</body></html>", encoding="utf-8")
            first_hash = hashlib.sha256(first.read_bytes()).hexdigest()
            second_hash = hashlib.sha256(second.read_bytes()).hexdigest()

            result = register_html_documents(
                root_dir=root_dir,
                source_id="camalanca_html",
                base_url="https://www.camalanca.it/",
                access_date="2026-05-11",
            )
            inventory = build_raw_document_inventory(root_dir=root_dir)
            sidecars = sorted((root_dir / ".document_sidecars").rglob("document.yaml"))
            payloads = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sidecars]
            first_after_hash = hashlib.sha256(first.read_bytes()).hexdigest()
            second_after_hash = hashlib.sha256(second.read_bytes()).hexdigest()

        self.assertEqual(result["registered_count"], 2)
        self.assertEqual(result["skipped_count"], 0)
        self.assertEqual(first_after_hash, first_hash)
        self.assertEqual(second_after_hash, second_hash)
        self.assertEqual(len(sidecars), 2)
        self.assertEqual(inventory["document_count"], 2)
        by_title = {payload["title"]: payload for payload in payloads}
        self.assertEqual(by_title["Ancilla Cavina"]["url"], "https://www.camalanca.it/ancilla-cavina.html")
        self.assertEqual(by_title["adelmo brini"]["content_hash"], second_hash)
        self.assertEqual(by_title["Ancilla Cavina"]["metadata"]["review_status"], "unreviewed")
        self.assertEqual(by_title["Ancilla Cavina"]["metadata"]["extraction_status"], "manual_review_required")
        self.assertNotIn("CandidateEvidenceClaim", str(payloads))

    def test_skips_existing_sidecar_without_overwrite(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            root_dir.mkdir()
            html = root_dir / "scheda.html"
            html.write_text("<html><head><title>Prima versione</title></head></html>", encoding="utf-8")

            first = register_html_documents(root_dir=root_dir, source_id="camalanca_html", access_date="2026-05-11")
            sidecar_path = Path(first["registered"][0]["sidecar_path"])
            before = sidecar_path.read_text(encoding="utf-8")
            html.write_text("<html><head><title>Seconda versione</title></head></html>", encoding="utf-8")
            second = register_html_documents(root_dir=root_dir, source_id="camalanca_html", access_date="2026-05-11")
            after = sidecar_path.read_text(encoding="utf-8")
            sidecar_count = len(list((root_dir / ".document_sidecars").rglob("document.yaml")))

        self.assertEqual(second["registered_count"], 0)
        self.assertEqual(second["skipped_count"], 1)
        self.assertEqual(after, before)
        self.assertEqual(sidecar_count, 1)

    def test_registered_html_flows_to_metadata_and_text_extraction(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            processed_dir = tmp_dir / "processed"
            root_dir.mkdir()
            html = root_dir / "ancilla-cavina" / "index.html"
            html.parent.mkdir()
            html.write_text(
                "<html><head><title>Ancilla Cavina</title><script>skip()</script></head>"
                "<body><h1>Ancilla Cavina</h1><p>Scheda locale.</p></body></html>",
                encoding="utf-8",
            )
            register_html_documents(
                root_dir=root_dir,
                source_id="camalanca_html",
                base_url="https://www.camalanca.it/",
                access_date="2026-05-11",
            )

            metadata_summary = extract_document_metadata(root_dir=root_dir, output_dir=metadata_dir)
            text_summary = extract_document_text(metadata_dir=metadata_dir, output_dir=processed_dir, raw_root_dir=root_dir)

        self.assertEqual(metadata_summary["document_count"], 1)
        self.assertEqual(text_summary["document_count"], 1)
        self.assertEqual(text_summary["extracted_count"], 1)
        self.assertEqual(text_summary["documents"][0]["claim_eligible"], True)


if __name__ == "__main__":
    unittest.main()
