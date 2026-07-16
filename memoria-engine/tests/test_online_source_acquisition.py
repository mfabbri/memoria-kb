from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

import yaml


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.online_source_acquisition import acquire_online_source_document, acquisition_summary
from caduti_fonti_report.models import SourceDocument


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


class OnlineSourceAcquisitionTests(unittest.TestCase):
    def test_acquires_partigiani_italia_related_image_document(self) -> None:
        image_url = "https://partigianiditalia.cultura.gov.it/wp-content/uploads/schede/balboni.jpg"
        document = SourceDocument(
            document_id="partigiani_italia:detail:1",
            source_id="partigiani_italia",
            title="Balboni, William",
            url="https://partigianiditalia.cultura.gov.it/persona/?id=abc",
            access_date="2026-06-06",
            raw_text="Balboni, William Dati anagrafici Nome: William",
            metadata={
                "partigiani_italia_image_urls_json": json.dumps(
                    [{"url": image_url, "alt": "Scheda Balboni William", "title": ""}],
                    ensure_ascii=False,
                )
            },
        )

        with workspace_temp_dir() as tmp_dir:
            acquired = acquire_online_source_document(
                document=document,
                root_dir=tmp_dir,
                profile_slug="balboni-william",
                profile_id="person:purocielo:balboni-william",
                image_fetcher=lambda url: (b"\xff\xd8fixture\xff\xd9", "image/jpeg"),
            )
            related = acquired["related_documents"][0]
            image_path = Path(related["file"])
            sidecar = yaml.safe_load(Path(related["sidecar"]).read_text(encoding="utf-8"))

        self.assertEqual(acquired["status"], "acquired")
        self.assertEqual(acquired["related_document_count"], 1)
        self.assertEqual(related["status"], "acquired")
        self.assertEqual(image_path.suffix, ".jpg")
        self.assertEqual(sidecar["metadata"]["document_type"], "online_detail_image")
        self.assertEqual(sidecar["metadata"]["document_class"], "image_scan")
        self.assertFalse(sidecar["metadata"]["claim_eligible"])
        self.assertEqual(sidecar["metadata"]["source_document_id"], "partigiani_italia:detail:1")
        self.assertEqual(sidecar["metadata"]["profile_id"], "person:purocielo:balboni-william")
        summary = acquisition_summary([acquired])
        self.assertEqual(summary["acquired_count"], 1)
        self.assertEqual(summary["related_acquired_count"], 1)
        self.assertEqual(summary["total_acquired_file_count"], 2)

    def test_acquires_related_image_even_when_text_is_empty(self) -> None:
        image_url = "https://partigianiditalia.cultura.gov.it/partigiani-rest-api/v1.4/media/card.jpg?key=abc&ip=127.0.0.1"
        document = SourceDocument(
            document_id="partigiani_italia:detail:empty",
            source_id="partigiani_italia",
            title="I PARTIGIANI D'ITALIA",
            url="https://partigianiditalia.cultura.gov.it/persona/?id=abc",
            access_date="2026-06-06",
            raw_text="",
            metadata={"partigiani_italia_image_urls_json": json.dumps([{"url": image_url}], ensure_ascii=False)},
        )

        with workspace_temp_dir() as tmp_dir:
            acquired = acquire_online_source_document(
                document=document,
                root_dir=tmp_dir,
                profile_slug="balboni-william",
                profile_id="person:purocielo:balboni-william",
                image_fetcher=lambda url: (b"\xff\xd8fixture\xff\xd9", "image/jpeg"),
            )
            related = acquired["related_documents"][0]
            image_path = Path(related["file"])
            image_exists = image_path.exists()

        self.assertEqual(acquired["status"], "skipped_empty_raw_text")
        self.assertEqual(acquired["related_document_count"], 1)
        self.assertTrue(image_exists)


if __name__ == "__main__":
    unittest.main()
