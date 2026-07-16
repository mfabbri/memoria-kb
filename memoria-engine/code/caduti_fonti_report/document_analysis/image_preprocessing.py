from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def preprocess_dark_foreground_for_ocr(
    *,
    file_path: Path,
    output_file: Path,
    mask_file: Path | None = None,
    median_background_size: int = 31,
    absolute_dark_threshold: int = 118,
    local_contrast_threshold: int = 22,
    median_cleanup_size: int = 3,
    overwrite: bool = False,
) -> dict[str, Any]:
    try:
        from PIL import Image, ImageFilter
    except ImportError as exc:  # pragma: no cover - exercised only without Pillow
        raise RuntimeError("Pillow non disponibile: impossibile preprocessare l'immagine.") from exc

    file_path = Path(file_path)
    output_file = Path(output_file)
    mask_file = Path(mask_file) if mask_file is not None else None
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"Immagine non trovata: {file_path}")
    if output_file.exists() and not overwrite:
        raise FileExistsError(f"Output gia' presente: {output_file}")
    if mask_file is not None and mask_file.exists() and not overwrite:
        raise FileExistsError(f"Maschera gia' presente: {mask_file}")
    if median_background_size < 3 or median_background_size % 2 == 0:
        raise ValueError("median_background_size deve essere dispari e >= 3.")
    if median_cleanup_size < 3 or median_cleanup_size % 2 == 0:
        raise ValueError("median_cleanup_size deve essere dispari e >= 3.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    if mask_file is not None:
        mask_file.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(file_path) as image:
        grayscale = image.convert("L")
        background = grayscale.filter(ImageFilter.MedianFilter(median_background_size))
        width, height = grayscale.size
        prepared = Image.new("L", grayscale.size, 255)
        mask = Image.new("L", grayscale.size, 0)
        source_pixels = grayscale.load()
        background_pixels = background.load()
        prepared_pixels = prepared.load()
        mask_pixels = mask.load()
        foreground_pixels = 0
        for y in range(height):
            for x in range(width):
                source_value = source_pixels[x, y]
                is_dark = source_value < absolute_dark_threshold
                is_locally_dark = (background_pixels[x, y] - source_value) > local_contrast_threshold
                if is_dark or is_locally_dark:
                    prepared_pixels[x, y] = 0
                    mask_pixels[x, y] = 255
                    foreground_pixels += 1
        prepared = prepared.filter(ImageFilter.MedianFilter(median_cleanup_size))
        mask = mask.filter(ImageFilter.MedianFilter(median_cleanup_size))
        prepared.save(output_file)
        if mask_file is not None:
            mask.save(mask_file)

    return {
        "@type": "ImageOcrPreprocessingResult",
        "preprocessing_method": "dark_foreground_binary",
        "source_file": str(file_path),
        "output_file": str(output_file),
        "mask_file": str(mask_file) if mask_file is not None else "",
        "created_at": datetime.now(UTC).isoformat(),
        "image_width": width,
        "image_height": height,
        "foreground_pixels": foreground_pixels,
        "foreground_percent": round((foreground_pixels / (width * height)) * 100, 4),
        "parameters": {
            "median_background_size": median_background_size,
            "absolute_dark_threshold": absolute_dark_threshold,
            "local_contrast_threshold": local_contrast_threshold,
            "median_cleanup_size": median_cleanup_size,
        },
        "review_status": "unreviewed",
        "notes": [
            "Derivata per OCR: conserva foreground scuro e forza watermark chiaro a sfondo.",
            "Non sostituisce il raw originale e non produce trascrizione o claim.",
        ],
    }


def write_preprocessing_report(*, report: dict[str, Any], output_json: Path) -> None:
    output_json = Path(output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea una derivata OCR scuro-su-bianco da una scansione.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--mask-file", default="")
    parser.add_argument("--report-json", default="")
    parser.add_argument("--median-background-size", type=int, default=31)
    parser.add_argument("--absolute-dark-threshold", type=int, default=118)
    parser.add_argument("--local-contrast-threshold", type=int, default=22)
    parser.add_argument("--median-cleanup-size", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        report = preprocess_dark_foreground_for_ocr(
            file_path=Path(args.file),
            output_file=Path(args.output_file),
            mask_file=Path(args.mask_file) if args.mask_file.strip() else None,
            median_background_size=args.median_background_size,
            absolute_dark_threshold=args.absolute_dark_threshold,
            local_contrast_threshold=args.local_contrast_threshold,
            median_cleanup_size=args.median_cleanup_size,
            overwrite=args.overwrite,
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    if args.report_json.strip():
        write_preprocessing_report(report=report, output_json=Path(args.report_json))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
