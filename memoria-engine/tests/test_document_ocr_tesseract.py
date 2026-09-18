from __future__ import annotations

import hashlib
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

from caduti_fonti_report.document_analysis.document_quality import assess_document_quality  # noqa: E402
from caduti_fonti_report.document_analysis.manual_registration import register_manual_document  # noqa: E402
from caduti_fonti_report.document_analysis.ocr_tesseract import run_document_ocr  # noqa: E402


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


class DocumentOcrTesseractTests(unittest.TestCase):
    def test_runs_tesseract_and_registers_external_ocr_without_touching_image(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t92.0\tNato\n"
                        "5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t88.0\tbrigata\n"
                    )
                )
            return completed(stdout="Nato il 28 gennaio 1920.\nMilito nella 36ma brigata.\n")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "2026" / "05" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_bytes = b"\xff\xd8\xffscan\xff\xd9"
            image_path.write_bytes(image_bytes)
            before_hash = hashlib.sha256(image_bytes).hexdigest()
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
                access_date="2026-05-16",
            )

            result = run_document_ocr(
                file_path=image_path,
                root_dir=raw_dir,
                output_dir=output_dir,
                language="ita",
                tesseract_path="tesseract",
                command_runner=fake_runner,
            )
            text_payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))
            after_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()

        self.assertEqual(after_hash, before_hash)
        self.assertEqual(calls[0], ["tesseract", str(image_path), "stdout", "-l", "ita"])
        self.assertEqual(calls[1], ["tesseract", str(image_path), "stdout", "-l", "ita", "tsv"])
        self.assertEqual(result["@type"], "DocumentOcrRegistration")
        self.assertEqual(result["ocr_engine"], "tesseract")
        self.assertEqual(result["ocr_quality_status"], "usable_for_preview")
        self.assertEqual(result["ocr_mean_confidence"], 90.0)
        self.assertEqual(text_payload["@type"], "ProcessedDocumentText")
        self.assertEqual(text_payload["transcription_method"], "external_ocr_unreviewed")
        self.assertEqual(text_payload["extraction_status"], "external_ocr_registered")
        self.assertEqual(text_payload["review_status"], "unreviewed")
        self.assertEqual(text_payload["ocr_quality_status"], "usable_for_preview")
        self.assertEqual(text_payload["ocr_word_count"], 2)
        self.assertEqual(text_payload["ocr_mean_confidence"], 90.0)
        self.assertEqual(text_payload["ocr_low_confidence_words_count"], 0)
        self.assertEqual(text_payload["ocr_layout_status"], "layout_detected")
        self.assertEqual(text_payload["ocr_page_height"], 1400)
        self.assertEqual(text_payload["ocr_layout_lines"][0]["review_status"], "unreviewed")
        self.assertIn("36ma brigata", text_payload["text"])
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(text_payload))
        self.assertNotIn("EvidenceClaim", json.dumps(text_payload))
        self.assertNotIn("verified_facts", json.dumps(text_payload))

    def test_ocr_text_feeds_quality_assessment_as_image_transcription(self) -> None:
        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t82.0\tTrascrizione\n"
                    )
                )
            return completed(stdout="Trascrizione OCR da rivedere.")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )
            run_document_ocr(
                file_path=image_path,
                root_dir=raw_dir,
                output_dir=output_dir,
                command_runner=fake_runner,
            )

            summary = assess_document_quality(metadata_dir=output_dir, text_dir=output_dir, output_dir=output_dir)
            quality = json.loads(Path(summary["documents"][0]["quality_path"]).read_text(encoding="utf-8"))

        self.assertEqual(quality["quality_status"], "ready_for_manual_review")
        self.assertEqual(quality["classification"], "image_transcription")
        self.assertFalse(quality["claim_allowed"])

    def test_rejects_sparse_low_confidence_text_before_registration(self) -> None:
        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91.0\tNato\n"
                        "5\t1\t1\t1\t1\t2\t0\t0\t10\t10\t24.0\t???\n"
                    )
                )
            return completed(stdout="Nato ???")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            with self.assertRaisesRegex(ValueError, "qualitativamente insufficiente"):
                run_document_ocr(
                    file_path=image_path,
                    root_dir=raw_dir,
                    output_dir=output_dir,
                    command_runner=fake_runner,
                )

        self.assertFalse(list(output_dir.rglob("*.text.json")))

    def test_single_low_confidence_token_does_not_fail_quality_gate(self) -> None:
        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(stdout=(
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t91\tTesto\n"
                    "5\t1\t1\t1\t1\t2\t12\t0\t10\t10\t89\tvalido\n"
                    "5\t1\t1\t1\t1\t3\t24\t0\t10\t10\t24\t???\n"
                ))
            return completed(stdout="Testo valido ???")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scansione", archival_reference="R-1")
            result = run_document_ocr(file_path=image_path, root_dir=raw_dir, output_dir=output_dir, command_runner=fake_runner)
            payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(payload["ocr_quality_gate_status"], "accepted")
        self.assertEqual(payload["ocr_quality_status"], "low_confidence")
        self.assertEqual(payload["ocr_low_confidence_words_count"], 1)

    def test_quality_gate_accepts_exactly_seventy_five_percent_low_confidence_words(self) -> None:
        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(stdout=(
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tuno\n"
                    "5\t1\t1\t1\t1\t2\t12\t0\t10\t10\t35\tdue\n"
                    "5\t1\t1\t1\t1\t3\t24\t0\t10\t10\t35\ttre\n"
                    "5\t1\t1\t1\t1\t4\t36\t0\t10\t10\t35\tquattro\n"
                ))
            return completed(stdout="uno due tre quattro")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scansione", archival_reference="R-1")
            result = run_document_ocr(file_path=image_path, root_dir=raw_dir, output_dir=output_dir, command_runner=fake_runner)
            payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(payload["ocr_quality_gate_status"], "accepted")
        self.assertEqual(payload["ocr_low_confidence_words_count"], 3)

    def test_quality_gate_rejects_more_than_seventy_five_percent_low_confidence_words(self) -> None:
        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(stdout=(
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t99\tuno\n"
                    "5\t1\t1\t1\t1\t2\t12\t0\t10\t10\t35\tdue\n"
                    "5\t1\t1\t1\t1\t3\t24\t0\t10\t10\t35\ttre\n"
                    "5\t1\t1\t1\t1\t4\t36\t0\t10\t10\t35\tquattro\n"
                    "5\t1\t1\t1\t1\t5\t48\t0\t10\t10\t35\tcinque\n"
                ))
            return completed(stdout="uno due tre quattro cinque")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "scan.png"
            image_path.parent.mkdir(parents=True)
            Image.new("RGB", (30, 30), color="white").save(image_path)
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scansione", archival_reference="R-1")
            with self.assertRaisesRegex(ValueError, "qualitativamente insufficiente"):
                run_document_ocr(file_path=image_path, root_dir=raw_dir, output_dir=output_dir, command_runner=fake_runner)
            self.assertFalse(list(output_dir.rglob("*.text.json")))

    def test_rejected_retry_preserves_existing_text_json_when_overwrite_requested(self) -> None:
        def accepted_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(stdout=(
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tTesto\n"
                    "5\t1\t1\t1\t1\t2\t12\t0\t10\t10\t90\tvalido\n"
                ))
            return completed(stdout="Testo valido")

        def rejected_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(stdout=(
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t12\t???\n"
                ))
            return completed(stdout="???")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "scan.png"
            image_path.parent.mkdir(parents=True)
            Image.new("RGB", (30, 30), color="white").save(image_path)
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scansione", archival_reference="R-1")
            first = run_document_ocr(file_path=image_path, root_dir=raw_dir, output_dir=output_dir, command_runner=accepted_runner)
            text_path = Path(first["text_path"])
            before = text_path.read_bytes()
            with self.assertRaisesRegex(ValueError, "qualitativamente insufficiente"):
                run_document_ocr(file_path=image_path, root_dir=raw_dir, output_dir=output_dir, overwrite=True, command_runner=rejected_runner)
            after = text_path.read_bytes()

        self.assertEqual(after, before)

    def test_passes_layout_options_and_extracts_footnote_candidates_from_tsv(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t100\t180\t40\t20\t92.0\tTesto\n"
                        "5\t1\t1\t1\t1\t2\t145\t180\t80\t20\t92.0\tprincipale\n"
                        "5\t1\t2\t1\t1\t1\t80\t1120\t12\t12\t86.0\t1\n"
                        "5\t1\t2\t1\t1\t2\t98\t1120\t30\t12\t84.0\tCfr.\n"
                        "5\t1\t2\t1\t1\t3\t135\t1120\t60\t12\t82.0\tRossi,\n"
                        "5\t1\t2\t1\t1\t4\t202\t1120\t40\t12\t80.0\t2005\n"
                    )
                )
            return completed(stdout="Testo principale. 1 Cfr. Rossi, 2005")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            result = run_document_ocr(
                file_path=image_path,
                root_dir=raw_dir,
                output_dir=output_dir,
                page_segmentation_mode="4",
                engine_mode="1",
                dpi="300",
                command_runner=fake_runner,
            )
            text_payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(calls[0], ["tesseract", str(image_path), "stdout", "-l", "ita", "--psm", "4", "--oem", "1", "--dpi", "300"])
        self.assertEqual(calls[1], ["tesseract", str(image_path), "stdout", "-l", "ita", "--psm", "4", "--oem", "1", "--dpi", "300", "tsv"])
        self.assertEqual(result["ocr_layout_status"], "layout_detected")
        self.assertEqual(text_payload["ocr_line_count"], 2)
        self.assertEqual(len(text_payload["ocr_footnote_candidates"]), 1)
        self.assertIn("Cfr. Rossi, 2005", text_payload["ocr_footnote_candidates"][0]["text"])
        self.assertIn("bottom_page_region", text_payload["ocr_footnote_candidates"][0]["reasons"])
        self.assertIn("reference_pattern", text_payload["ocr_reference_candidates"][0]["reasons"])
        self.assertEqual(text_payload["ocr_footnote_candidates"][0]["review_status"], "unreviewed")
        self.assertNotIn("EvidenceClaim", json.dumps(text_payload))

    def test_persists_ordered_tsv_layout_lines_separately_from_candidates(self) -> None:
        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t2\t1\t4\t2\t170\t1120\t40\t12\t80.0\t2005\n"
                        "5\t1\t1\t1\t2\t2\t150\t180\t80\t20\t94.0\tprincipale\n"
                        "5\t1\t2\t1\t4\t1\t100\t1120\t60\t12\t84.0\tCfr.\n"
                        "5\t1\t1\t1\t2\t1\t100\t180\t40\t20\t92.0\tTesto\n"
                    )
                )
            return completed(stdout="Testo principale. Cfr. 2005")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            result = run_document_ocr(
                file_path=image_path,
                root_dir=raw_dir,
                output_dir=output_dir,
                command_runner=fake_runner,
            )
            text_payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))

        layout_lines = text_payload["ocr_layout_lines"]
        self.assertEqual([line["text"] for line in layout_lines], ["Testo principale", "Cfr. 2005"])
        self.assertEqual([line["read_order"] for line in layout_lines], [1, 2])
        self.assertEqual({line["read_order_status"] for line in layout_lines}, {"inferred"})
        self.assertEqual({line["read_order_basis"] for line in layout_lines}, {"page_top_then_left_then_tsv_hierarchy"})
        self.assertEqual({line["source_document_id"] for line in layout_lines}, {result["source_document_id"]})
        self.assertEqual(layout_lines[0]["ocr_line_id"], "tesseract-line-p1-b1-par1-l2")
        self.assertEqual(layout_lines[0]["page_id"], "tesseract-page-1")
        self.assertEqual(layout_lines[1]["region_id"], "tesseract-region-p1-b2-par1-l4")
        self.assertEqual(layout_lines[1]["left"], 100)
        self.assertEqual(layout_lines[1]["top"], 1120)
        self.assertEqual(layout_lines[1]["width"], 110)
        self.assertEqual(layout_lines[1]["height"], 12)
        self.assertEqual(layout_lines[1]["confidence"], 82.0)
        self.assertEqual({line["review_status"] for line in layout_lines}, {"unreviewed"})
        self.assertEqual(len(text_payload["ocr_reference_candidates"]), 1)
        self.assertEqual(text_payload["ocr_reference_candidates"][0]["ocr_line_id"], layout_lines[1]["ocr_line_id"])
        self.assertEqual(text_payload["ocr_reference_candidates"][0]["source_document_id"], result["source_document_id"])
        self.assertNotEqual(text_payload["ocr_layout_lines"], text_payload["ocr_reference_candidates"])

    def test_falls_back_to_sparse_text_psm_when_requested_psm_returns_empty(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1] == "tsv":
                self.assertIn("--psm", command)
                self.assertEqual(command[command.index("--psm") + 1], "12")
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t63.0\tPurocielo\n"
                    )
                )
            if "--psm" in command and command[command.index("--psm") + 1] == "4":
                return completed(stdout=" \n ", stderr="Empty page!!")
            return completed(stdout="Purocielo testo recuperato con PSM 12.")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            result = run_document_ocr(
                file_path=image_path,
                root_dir=raw_dir,
                output_dir=output_dir,
                page_segmentation_mode="4",
                command_runner=fake_runner,
            )
            text_payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(result["ocr_effective_page_segmentation_mode"], "12")
        self.assertEqual(text_payload["ocr_effective_page_segmentation_mode"], "12")
        self.assertEqual(text_payload["text"], "Purocielo testo recuperato con PSM 12.")
        self.assertEqual(text_payload["ocr_fallback_attempts"][0]["status"], "empty")
        self.assertEqual(text_payload["ocr_fallback_attempts"][1]["status"], "selected")
        self.assertEqual(calls[0], ["tesseract", str(image_path), "stdout", "-l", "ita", "--psm", "4"])
        self.assertEqual(calls[1], ["tesseract", str(image_path), "stdout", "-l", "ita", "--psm", "12"])
        self.assertEqual(calls[2], ["tesseract", str(image_path), "stdout", "-l", "ita", "--psm", "12", "tsv"])
        self.assertNotIn("EvidenceClaim", json.dumps(text_payload))

    def test_quality_retry_selects_alternate_psm_after_diffuse_noise(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            mode = command[command.index("--psm") + 1] if "--psm" in command else ""
            if command[-1] == "tsv":
                if mode == "6":
                    return completed(stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t11\t???\n"
                    ))
                return completed(stdout=(
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t82\tTesto\n"
                    "5\t1\t1\t1\t1\t2\t12\t0\t10\t10\t84\tleggibile\n"
                ))
            return completed(stdout="%%%" if mode == "6" else "Testo leggibile")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scansione", archival_reference="R-1")
            result = run_document_ocr(file_path=image_path, root_dir=raw_dir, output_dir=output_dir, page_segmentation_mode="6", command_runner=fake_runner)
            payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))

        self.assertEqual(result["ocr_effective_page_segmentation_mode"], "12")
        self.assertEqual([attempt["status"] for attempt in payload["ocr_fallback_attempts"]], ["quality_rejected", "selected"])
        self.assertEqual(len(calls), 4)
        self.assertEqual(payload["ocr_quality_gate_status"], "accepted")

    def test_quality_retry_refuses_all_candidates_without_creating_json(self) -> None:
        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(stdout=(
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                    "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
                    "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t12\t???\n"
                ))
            return completed(stdout="???")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "scan.png"
            image_path.parent.mkdir(parents=True)
            Image.new("RGB", (30, 30), color="white").save(image_path)
            register_manual_document(file_path=image_path, source_id="manual_uploads", title="Scansione", archival_reference="R-1")
            with self.assertRaisesRegex(ValueError, "qualitativamente insufficiente"):
                run_document_ocr(file_path=image_path, root_dir=raw_dir, output_dir=output_dir, command_runner=fake_runner)
            self.assertFalse(list(output_dir.rglob("*.text.json")))

    def test_optional_region_ocr_uses_temporary_preprocessed_crops_without_touching_raw(self) -> None:
        calls: list[list[str]] = []

        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            image_arg = command[1]
            if command[-1] == "tsv":
                return completed(
                    stdout=(
                        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                        "1\t1\t0\t0\t0\t0\t0\t0\t1000\t1400\t-1\t\n"
                        "5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90.0\tPagina\n"
                    )
                )
            if "bottom_region" in image_arg:
                return completed(stdout="1 Cfr. Rossi, 2005, p. 42")
            if "left_page" in image_arg:
                return completed(stdout="Testo colonna sinistra")
            if "right_page" in image_arg:
                return completed(stdout="Testo colonna destra")
            return completed(stdout="Testo pagina intera")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            Image.new("RGB", (800, 1200), color="white").save(image_path)
            before_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            result = run_document_ocr(
                file_path=image_path,
                root_dir=raw_dir,
                output_dir=output_dir,
                enable_region_ocr=True,
                command_runner=fake_runner,
            )
            text_payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))
            after_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()

        self.assertEqual(after_hash, before_hash)
        self.assertEqual(result["ocr_region_status"], "regions_extracted")
        self.assertEqual(text_payload["ocr_region_status"], "regions_extracted")
        self.assertEqual([output["region"] for output in text_payload["ocr_region_outputs"]], ["bottom_region", "left_page", "right_page"])
        self.assertEqual(text_payload["ocr_region_outputs"][0]["text"], "1 Cfr. Rossi, 2005, p. 42")
        self.assertTrue(text_payload["ocr_region_outputs"][0]["reference_signal"])
        self.assertTrue(any("bottom_region.png" in call[1] for call in calls))
        self.assertNotIn("EvidenceClaim", json.dumps(text_payload))

    def test_preprocess_before_ocr_uses_temporary_image_without_touching_raw(self) -> None:
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
            return completed(stdout="Documento preprocessato")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.png"
            image_path.parent.mkdir(parents=True)
            Image.new("RGB", (120, 80), color="white").save(image_path)
            before_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            result = run_document_ocr(
                file_path=image_path,
                root_dir=raw_dir,
                output_dir=output_dir,
                preprocess_before_ocr=True,
                command_runner=fake_runner,
            )
            text_payload = json.loads(Path(result["text_path"]).read_text(encoding="utf-8"))
            after_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()

        self.assertEqual(after_hash, before_hash)
        self.assertEqual(result["ocr_preprocessing_status"], "preprocessed_temporary")
        self.assertEqual(text_payload["ocr_preprocessing_status"], "preprocessed_temporary")
        self.assertEqual(text_payload["ocr_preprocessing_method"], "dark_foreground_binary")
        self.assertEqual(text_payload["ocr_input_source"], "temporary_preprocessed_image")
        self.assertEqual(text_payload["text"], "Documento preprocessato")
        self.assertNotIn("EvidenceClaim", json.dumps(text_payload))

    def test_missing_tsv_confidence_rejects_text_before_registration(self) -> None:
        def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "tsv":
                return completed(stderr="tsv unavailable", returncode=1)
            return completed(stdout="Testo OCR presente.")

        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            output_dir = tmp_dir / "processed"
            image_path = raw_dir / "manual_uploads" / "scan.jpg"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")
            register_manual_document(
                file_path=image_path,
                source_id="manual_uploads",
                title="Scansione manuale",
                archival_reference="RH 20/10/199 0006",
            )

            with self.assertRaisesRegex(ValueError, "qualitativamente insufficiente"):
                run_document_ocr(
                    file_path=image_path,
                    root_dir=raw_dir,
                    output_dir=output_dir,
                    command_runner=fake_runner,
                )

        self.assertFalse(list(output_dir.rglob("*.text.json")))

    def test_reports_missing_tesseract_readably(self) -> None:
        def missing_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError("missing")

        with workspace_temp_dir() as tmp_dir:
            image_path = tmp_dir / "scan.jpg"
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")

            with self.assertRaisesRegex(FileNotFoundError, "Tesseract non trovato"):
                run_document_ocr(file_path=image_path, tesseract_path="missing-tesseract", command_runner=missing_runner)

    def test_refuses_empty_or_failed_ocr(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            image_path = tmp_dir / "scan.jpg"
            image_path.write_bytes(b"\xff\xd8\xffscan\xff\xd9")

            with self.assertRaisesRegex(ValueError, "OCR Tesseract vuoto"):
                run_document_ocr(file_path=image_path, command_runner=lambda command: completed(stdout=" \n "))

            with self.assertRaisesRegex(RuntimeError, "OCR Tesseract fallito"):
                run_document_ocr(file_path=image_path, command_runner=lambda command: completed(stderr="bad image", returncode=1))


if __name__ == "__main__":
    unittest.main()
