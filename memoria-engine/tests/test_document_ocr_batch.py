from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.manual_registration import register_manual_document  # noqa: E402
from caduti_fonti_report.document_analysis.ocr_batch import run_document_ocr_batch, write_batch_report  # noqa: E402


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


def completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["tesseract"], returncode=returncode, stdout=stdout, stderr=stderr)


class DocumentOcrBatchTests(unittest.TestCase):
    def test_batch_processes_registered_images_recursively_and_reports_skips(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91.0\tDocumento\n"
                    )
                )
            return completed(stdout=f"OCR {Path(command[1]).stem}")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            first = raw_dir / "set-a" / "scan-a.jpg"
            second = raw_dir / "set-b" / "nested" / "scan-b.jpeg"
            missing_sidecar = raw_dir / "loose.jpg"
            first.parent.mkdir(parents=True, exist_ok=True)
            second.parent.mkdir(parents=True, exist_ok=True)
            missing_sidecar.parent.mkdir(parents=True, exist_ok=True)
            first.write_bytes(b"\xff\xd8\xffscan-a\xff\xd9")
            second.write_bytes(b"\xff\xd8\xffscan-b\xff\xd9")
            missing_sidecar.write_bytes(b"\xff\xd8\xffloose\xff\xd9")
            register_manual_document(file_path=first, source_id="manual_uploads", title="Scan A", archival_reference="A")
            register_manual_document(file_path=second, source_id="manual_uploads", title="Scan B", archival_reference="B")

            report = run_document_ocr_batch(
                root_dir=raw_dir,
                output_dir=output_dir,
                max_workers=2,
                command_runner=fake_runner,
            )
            processed = [item for item in report["documents"] if item["status"] == "processed"]
            skipped = [item for item in report["documents"] if item["status"] == "skipped_missing_sidecar"]
            text_payloads = [json.loads(Path(item["text_path"]).read_text(encoding="utf-8")) for item in processed]

        self.assertEqual(report["@type"], "DocumentOcrBatchReport")
        self.assertEqual(report["max_workers"], 2)
        self.assertEqual(report["summary"]["total"], 3)
        self.assertEqual(report["summary"]["processed"], 2)
        self.assertEqual(report["summary"]["skipped_missing_sidecar"], 1)
        self.assertEqual(len(processed), 2)
        self.assertEqual(len(skipped), 1)
        self.assertTrue(all(payload["transcription_method"] == "external_ocr_unreviewed" for payload in text_payloads))
        self.assertTrue(all(payload["review_status"] == "unreviewed" for payload in text_payloads))
        self.assertNotIn("EvidenceClaim", json.dumps(report))
        self.assertGreaterEqual(len(calls), 4)

    def test_batch_records_unreadable_sidecar_without_stopping_collection(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91.0\tDocumento\n"
                    )
                )
            return completed(stdout="OCR valido")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            broken = raw_dir / "set-a" / "broken.jpg"
            valid = raw_dir / "set-b" / "valid.jpg"
            broken.parent.mkdir(parents=True)
            valid.parent.mkdir(parents=True)
            broken.write_bytes(b"\xff\xd8\xffbroken\xff\xd9")
            valid.write_bytes(b"\xff\xd8\xffvalid\xff\xd9")
            broken.with_name("broken.jpg.document.yaml").write_text(
                "source_id: manual_uploads\nbad: \x8f\n",
                encoding="utf-8",
            )
            register_manual_document(file_path=valid, source_id="manual_uploads", title="Valid", archival_reference="V")

            report = run_document_ocr_batch(root_dir=raw_dir, output_dir=output_dir, command_runner=fake_runner)
            unreadable = [item for item in report["documents"] if item["status"] == "skipped_unreadable_sidecar"]
            processed = [item for item in report["documents"] if item["status"] == "processed"]

        self.assertEqual(report["summary"]["total"], 2)
        self.assertEqual(report["summary"]["skipped_unreadable_sidecar"], 1)
        self.assertEqual(report["summary"]["processed"], 1)
        self.assertEqual(len(unreadable), 1)
        self.assertEqual(len(processed), 1)
        self.assertIn("ReaderError", unreadable[0]["reason"])
        self.assertIn("broken.jpg.document.yaml", unreadable[0]["sidecar"])
        self.assertGreaterEqual(len(calls), 2)

    def test_batch_skips_existing_text_without_overwrite(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91.0\tDocumento\n"
                    )
                )
            return completed(stdout="OCR")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "set-a" / "scan-a.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scan A", archival_reference="A")

            first_report = run_document_ocr_batch(root_dir=raw_dir, output_dir=output_dir, command_runner=fake_runner)
            calls_after_first = len(calls)
            second_report = run_document_ocr_batch(root_dir=raw_dir, output_dir=output_dir, command_runner=fake_runner)

        self.assertEqual(first_report["summary"]["processed"], 1)
        self.assertEqual(second_report["summary"]["skipped_existing_text"], 1)
        self.assertEqual(len(calls), calls_after_first)

    def test_batch_can_preprocess_images_before_ocr(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            self.assertIn("preprocessed.png", command[1])
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91.0\tDocumento\n"
                    )
                )
            return completed(stdout="OCR preprocessato")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "set-a" / "scan-a.png"
            image_path.parent.mkdir(parents=True)
            Image.new("RGB", (120, 80), color="white").save(image_path)
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scan A", archival_reference="A")

            report = run_document_ocr_batch(
                root_dir=raw_dir,
                output_dir=output_dir,
                preprocess_before_ocr=True,
                command_runner=fake_runner,
            )
            processed = [item for item in report["documents"] if item["status"] == "processed"]
            text_payload = json.loads(Path(processed[0]["text_path"]).read_text(encoding="utf-8"))

        self.assertTrue(report["preprocess_before_ocr"])
        self.assertEqual(report["summary"]["processed"], 1)
        self.assertEqual(processed[0]["ocr_preprocessing_status"], "preprocessed_temporary")
        self.assertEqual(text_payload["ocr_preprocessing_status"], "preprocessed_temporary")
        self.assertEqual(text_payload["ocr_input_source"], "temporary_preprocessed_image")
        self.assertGreaterEqual(len(calls), 2)

    def test_file_exists_during_registration_is_reported_as_existing_text_skip(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91.0\tDocumento\n"
                    )
                )
            return completed(stdout="OCR")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "set-a" / "scan-a.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scan A", archival_reference="A")

            metadata_dir = output_dir / "legacy_source"
            metadata_dir.mkdir(parents=True)
            metadata = {
                "@type": "ProcessedDocumentMetadata",
                "source_id": "legacy_source",
                "source_document_id": "legacy-source:scan-a",
                "title": "Scan A",
                "document_class": "image_scan",
                "claim_eligible": False,
                "review_status": "unreviewed",
                "raw_file": "set-a\\scan-a.jpg",
                "media_type": "image/jpeg",
            }
            (metadata_dir / "legacy-source-scan-a.metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            existing_text = metadata_dir / "legacy-source-scan-a.text.json"
            existing_text.write_text("{}", encoding="utf-8")

            report = run_document_ocr_batch(root_dir=raw_dir, output_dir=output_dir, command_runner=fake_runner)

        self.assertEqual(report["summary"]["error"], 0)
        self.assertEqual(report["summary"]["skipped_existing_text"], 1)
        self.assertEqual(report["documents"][0]["status"], "skipped_existing_text")
        self.assertIn("Testo processato gia' presente", report["documents"][0]["reason"])
        self.assertIn(str(existing_text), report["documents"][0]["existing_text_path"])
        self.assertGreaterEqual(len(calls), 2)

    def test_writes_json_and_markdown_batch_report(self) -> None:
        report = {
            "@type": "DocumentOcrBatchReport",
            "root_dir": "raw",
            "output_dir": "processed",
            "max_workers": 2,
            "summary": {"total": 1, "processed": 1},
            "documents": [{"status": "processed", "file": "scan.jpg", "sidecar": "document.yaml", "text_path": "scan.text.json"}],
        }
        with workspace_temp_dir() as tmp_dir:
            output_json = tmp_dir / "ocr_batch_report.json"
            output_md = tmp_dir / "ocr_batch_report.md"
            write_batch_report(report=report, output_json=output_json, output_md=output_md)
            json_payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(json_payload["@type"], "DocumentOcrBatchReport")
        self.assertIn("# OCR batch preview", markdown)
        self.assertIn("scan.jpg", markdown)

    def test_batch_writes_progress_to_callback_and_log_file(self) -> None:
        calls: list[list[str]] = []
        progress_lines: list[str] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91.0\tDocumento\n"
                    )
                )
            return completed(stdout=f"OCR {Path(command[1]).stem}")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            log_file = tmp_dir / "logs" / "ocr_batch.log"
            first = raw_dir / "set-a" / "scan-a.jpg"
            second = raw_dir / "set-b" / "scan-b.jpg"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_bytes(b"\xff\xd8\xffscan-a\xff\xd9")
            second.write_bytes(b"\xff\xd8\xffscan-b\xff\xd9")
            register_manual_document(file_path=first, source_id="manual_uploads", title="Scan A", archival_reference="A")
            register_manual_document(file_path=second, source_id="manual_uploads", title="Scan B", archival_reference="B")

            report = run_document_ocr_batch(
                root_dir=raw_dir,
                output_dir=output_dir,
                max_workers=1,
                command_runner=fake_runner,
                progress_callback=progress_lines.append,
                log_file=log_file,
                progress_every=1,
            )
            log_text = log_file.read_text(encoding="utf-8")

        self.assertEqual(report["summary"]["processed"], 2)
        self.assertEqual(report["progress_every"], 1)
        self.assertEqual(report["log_file"], str(log_file))
        self.assertTrue(any("RUN START ocr_batch" in line for line in progress_lines))
        self.assertTrue(any("COLLECT END image_candidates total=2 pending=2" in line for line in progress_lines))
        self.assertTrue(any("METADATA PROGRESS metadata inventory inventory sidecars start count=2" in line for line in progress_lines))
        self.assertTrue(any("METADATA PROGRESS metadata write done processed=2" in line for line in progress_lines))
        self.assertTrue(any("OCR START pending=2 workers=1" in line for line in progress_lines))
        self.assertEqual(sum("OCR ITEM START" in line for line in progress_lines), 2)
        self.assertEqual(sum("OCR ITEM END" in line for line in progress_lines), 2)
        self.assertEqual(sum("OCR PROGRESS" in line for line in progress_lines), 2)
        self.assertTrue(any("RUN END ocr_batch status=completed" in line for line in progress_lines))
        self.assertIn("RUN START ocr_batch", log_text)
        self.assertIn("METADATA PROGRESS metadata write done processed=2", log_text)
        self.assertIn("OCR ITEM START index=1/2", log_text)
        self.assertIn("OCR ITEM END index=2/2", log_text)
        self.assertIn("OCR PROGRESS completed=2/2", log_text)
        self.assertGreaterEqual(len(calls), 4)


if __name__ == "__main__":
    unittest.main()
