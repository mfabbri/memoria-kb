from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.image_preprocessing import (  # noqa: E402
    preprocess_dark_foreground_for_ocr,
    write_preprocessing_report,
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


class ImagePreprocessingTests(unittest.TestCase):
    def test_dark_foreground_preprocessing_keeps_dark_text_and_drops_light_overlay(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            source = tmp_dir / "scan.jpg"
            output = tmp_dir / "scan.ocr.png"
            mask = tmp_dir / "scan.mask.png"
            image = Image.new("RGB", (220, 120), color=(190, 170, 115))
            draw = ImageDraw.Draw(image)
            draw.text((20, 25), "DARK", fill=(25, 25, 25))
            draw.text((20, 65), "WATERMARK", fill=(235, 235, 225))
            image.save(source)

            report = preprocess_dark_foreground_for_ocr(
                file_path=source,
                output_file=output,
                mask_file=mask,
                median_background_size=9,
                absolute_dark_threshold=110,
                local_contrast_threshold=18,
            )
            processed = Image.open(output).convert("L")
            output_exists = output.exists()
            mask_exists = mask.exists()

        self.assertTrue(output_exists)
        self.assertTrue(mask_exists)
        self.assertEqual(report["preprocessing_method"], "dark_foreground_binary")
        dark_text_pixels = sum(
            1 for y in range(20, 45) for x in range(15, 70) if processed.getpixel((x, y)) == 0
        )
        watermark_pixels = sum(
            1 for y in range(60, 88) for x in range(15, 110) if processed.getpixel((x, y)) == 0
        )
        self.assertGreater(dark_text_pixels, 10)
        self.assertLess(watermark_pixels, 10)

    def test_refuses_existing_output_without_overwrite(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            source = tmp_dir / "scan.jpg"
            output = tmp_dir / "scan.ocr.png"
            Image.new("RGB", (20, 20), color="white").save(source)
            output.write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                preprocess_dark_foreground_for_ocr(file_path=source, output_file=output)

    def test_writes_report_json(self) -> None:
        report = {"@type": "ImageOcrPreprocessingResult", "review_status": "unreviewed"}
        with workspace_temp_dir() as tmp_dir:
            output_json = tmp_dir / "report.json"
            write_preprocessing_report(report=report, output_json=output_json)
            payload = json.loads(output_json.read_text(encoding="utf-8"))

        self.assertEqual(payload["review_status"], "unreviewed")


if __name__ == "__main__":
    unittest.main()
