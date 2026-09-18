from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import struct
import tempfile
import unittest
import zlib
import base64
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "code"))

from caduti_fonti_report.document_analysis.ocr_benchmark import (  # noqa: E402
    NORMALIZATION_ID,
    QWEN_OCR_TRANSCRIPTION_PROMPT,
    evaluate_ocr_benchmark,
    load_ocr_benchmark_manifest,
    run_qwen_ollama_ocr_benchmark,
    run_tesseract_ocr_benchmark,
)


FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "ocr_benchmark"


class OcrBenchmarkTests(unittest.TestCase):
    def test_evaluates_synthetic_cases_with_deterministic_metrics_and_provenance(self) -> None:
        outputs = {
            "clean-text": "Documento sintetico numero quarantadue Questa riga verifica la trascrizione pulita",
            "degraded-text": "Documento sintetico degradato Una parola resta nella scansione di inventata prova",
            "mixed-table-layout": "Registro sintetico Codice Stato Nota ALFA completo prova BETA parziale verifica Fine del registro",
        }

        first = evaluate_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", ocr_outputs=outputs)
        second = evaluate_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", ocr_outputs=outputs)

        self.assertEqual(first, second)
        self.assertEqual(first["normalization"], NORMALIZATION_ID)
        self.assertTrue(first["synthetic_dataset"])
        self.assertEqual([case["fixture_id"] for case in first["cases"]], ["clean-text", "degraded-text", "mixed-table-layout"])
        self.assertEqual(first["cases"][0]["metrics"]["text_accuracy"], 1.0)
        degraded = first["cases"][1]["metrics"]
        self.assertEqual(degraded["omitted_token_count"], 1)
        self.assertEqual(degraded["added_token_count"], 1)
        self.assertGreater(degraded["invention_rate"], 0.0)
        provenance = first["dataset_provenance"]
        self.assertEqual(provenance["manifest_sha256"], self._sha256(FIXTURE_DIR / "manifest.json"))
        self.assertEqual(provenance["fixtures"][0]["ground_truth_sha256"], self._sha256(FIXTURE_DIR / "clean-text.txt"))
        self.assertEqual(provenance["fixtures"][0]["image_sha256"], self._sha256(FIXTURE_DIR / "clean-text.png"))
        self.assertEqual(provenance["fixtures"][2]["image_dimensions"], {"width": 1200, "height": 1600})
        self.assertEqual(provenance["fixtures"][2]["image_format"], "png")

    def test_metrics_count_missing_reference_tokens_and_added_tokens_separately(self) -> None:
        outputs = self._exact_outputs()
        outputs["clean-text"] = "Documento sintetico numero quarantadue Questa riga verifica trascrizione pulita extra"

        report = evaluate_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", ocr_outputs=outputs)

        metrics = report["cases"][0]["metrics"]
        self.assertEqual(metrics["omitted_token_count"], 1)
        self.assertEqual(metrics["added_token_count"], 1)
        self.assertLess(metrics["reference_token_coverage"], 1.0)
        self.assertEqual(metrics["output_length_completeness"], 1.0)
        self.assertGreater(metrics["invention_rate"], 0.0)

    def test_fails_closed_when_an_output_is_missing_or_manifest_is_not_synthetic(self) -> None:
        outputs = self._exact_outputs()
        outputs.pop("clean-text")
        with self.assertRaisesRegex(ValueError, "Output OCR mancante"):
            evaluate_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", ocr_outputs=outputs)

        invalid = ROOT_DIR / ".tmp-tests" / "ocr-benchmark-invalid-manifest.json"
        invalid.parent.mkdir(parents=True, exist_ok=True)
        invalid.write_text(json.dumps({"dataset_id": "bad", "synthetic": False, "cases": []}), encoding="utf-8")
        self.addCleanup(invalid.unlink, missing_ok=True)
        with self.assertRaisesRegex(ValueError, "sintetiche"):
            load_ocr_benchmark_manifest(invalid)

    def test_empty_output_has_no_invention_and_empty_reference_cases_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "empty.txt").write_text("", encoding="utf-8")
            (fixture_dir / "words.txt").write_text("uno due", encoding="utf-8")
            self._write_png(fixture_dir / "image.png")
            manifest = fixture_dir / "manifest.json"
            manifest.write_text(json.dumps({"dataset_id": "empty-cases", "synthetic": True, "cases": [
                self._case("empty", "empty.txt"),
                self._case("empty-output", "empty.txt"),
                self._case("words", "words.txt"),
            ]}), encoding="utf-8")

            report = evaluate_ocr_benchmark(
                manifest_path=manifest,
                ocr_outputs={"empty": "", "empty-output": "inventato", "words": ""},
            )

        empty_metrics = report["cases"][0]["metrics"]
        empty_output_metrics = report["cases"][1]["metrics"]
        words_metrics = report["cases"][2]["metrics"]
        self.assertEqual(empty_metrics["text_accuracy"], 1.0)
        self.assertEqual(empty_metrics["reference_token_coverage"], 1.0)
        self.assertEqual(empty_metrics["output_length_completeness"], 1.0)
        self.assertEqual(empty_metrics["invention_rate"], 0.0)
        self.assertEqual(empty_output_metrics["text_accuracy"], 0.0)
        self.assertEqual(empty_output_metrics["reference_token_coverage"], 0.0)
        self.assertEqual(empty_output_metrics["output_length_completeness"], 0.0)
        self.assertEqual(empty_output_metrics["invention_rate"], 1.0)
        self.assertEqual(words_metrics["text_accuracy"], 0.0)
        self.assertEqual(words_metrics["reference_token_coverage"], 0.0)
        self.assertEqual(words_metrics["output_length_completeness"], 0.0)
        self.assertEqual(words_metrics["invention_rate"], 0.0)

    def test_rejects_unknown_outputs_and_ground_truth_paths_outside_fixture_directory(self) -> None:
        outputs = self._exact_outputs()
        outputs["unknown"] = "testo"
        with self.assertRaisesRegex(ValueError, "sconosciuta"):
            evaluate_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", ocr_outputs=outputs)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture_dir = root / "fixtures"
            fixture_dir.mkdir()
            outside = root / "outside.txt"
            outside.write_text("fuori", encoding="utf-8")
            (fixture_dir / "inside.txt").write_text("dentro", encoding="utf-8")
            self._write_png(fixture_dir / "image.png")
            traversal_manifest = fixture_dir / "traversal.json"
            traversal_manifest.write_text(json.dumps({"dataset_id": "traversal", "synthetic": True, "cases": [
                self._case("case", "../outside.txt"),
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non sicuro"):
                evaluate_ocr_benchmark(manifest_path=traversal_manifest, ocr_outputs={"case": "fuori"})

            drive_manifest = fixture_dir / "drive.json"
            drive_manifest.write_text(json.dumps({"dataset_id": "drive", "synthetic": True, "cases": [
                self._case("case", "C:\\\\outside.txt"),
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non sicuro"):
                load_ocr_benchmark_manifest(drive_manifest)

            link = fixture_dir / "outside-link.txt"
            try:
                link.symlink_to(outside)
            except OSError:
                link_created = False
            else:
                link_created = True
            if link_created:
                link_manifest = fixture_dir / "link.json"
                link_manifest.write_text(json.dumps({"dataset_id": "link", "synthetic": True, "cases": [
                    self._case("case", "outside-link.txt"),
                ]}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "fuori dalla directory"):
                    evaluate_ocr_benchmark(manifest_path=link_manifest, ocr_outputs={"case": "fuori"})

            image_link = fixture_dir / "outside-image-link.png"
            outside_image = root / "outside.png"
            outside_image.write_bytes((fixture_dir / "image.png").read_bytes())
            try:
                image_link.symlink_to(outside_image)
            except OSError:
                image_link_created = False
            else:
                image_link_created = True
            if image_link_created:
                image_link_manifest = fixture_dir / "image-link.json"
                image_link_manifest.write_text(json.dumps({"dataset_id": "image-link", "synthetic": True, "cases": [
                    self._case("case", "inside.txt", image_file="outside-image-link.png"),
                ]}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Immagine fuori dalla directory"):
                    evaluate_ocr_benchmark(manifest_path=image_link_manifest, ocr_outputs={"case": "dentro"})

            image_traversal_manifest = fixture_dir / "image-traversal.json"
            image_traversal_manifest.write_text(json.dumps({"dataset_id": "image-traversal", "synthetic": True, "cases": [
                self._case("case", "inside.txt", image_file="../outside.png"),
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "image_file non sicuro"):
                evaluate_ocr_benchmark(manifest_path=image_traversal_manifest, ocr_outputs={"case": "dentro"})

    def test_rejects_corrupted_png_and_manifest_dimension_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_dir = Path(tmp)
            (fixture_dir / "truth.txt").write_text("testo", encoding="utf-8")
            self._write_png(fixture_dir / "image.png")
            manifest = fixture_dir / "manifest.json"
            manifest.write_text(json.dumps({"dataset_id": "png-check", "synthetic": True, "cases": [
                self._case("case", "truth.txt"),
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Dimensioni raster non coerenti"):
                mismatched = self._case("case", "truth.txt")
                mismatched["image_dimensions"] = {"width": 2, "height": 1}
                manifest.write_text(json.dumps({"dataset_id": "png-size", "synthetic": True, "cases": [mismatched]}), encoding="utf-8")
                evaluate_ocr_benchmark(manifest_path=manifest, ocr_outputs={"case": "testo"})

            image = fixture_dir / "image.png"
            image.write_bytes(image.read_bytes()[:-1])
            manifest.write_text(json.dumps({"dataset_id": "png-truncated", "synthetic": True, "cases": [
                self._case("case", "truth.txt"),
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "troncato|IEND"):
                evaluate_ocr_benchmark(manifest_path=manifest, ocr_outputs={"case": "testo"})

            self._write_png(image, filter_byte=5)
            with self.assertRaisesRegex(ValueError, "Filtro PNG non valido"):
                evaluate_ocr_benchmark(manifest_path=manifest, ocr_outputs={"case": "testo"})

    def test_runs_tesseract_fixture_commands_and_records_provenance(self) -> None:
        commands: list[list[str]] = []

        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            if command == ["tesseract-local", "--version"]:
                return subprocess.CompletedProcess(command, 0, "tesseract 5.5.0\n", "")
            fixture_id = Path(command[1]).stem
            return subprocess.CompletedProcess(command, 0, self._exact_outputs()[fixture_id], "")

        report = run_tesseract_ocr_benchmark(
            manifest_path=FIXTURE_DIR / "manifest.json",
            tesseract_path="tesseract-local",
            language="ita",
            page_segmentation_mode="6",
            engine_mode="1",
            command_runner=runner,
        )

        self.assertEqual(report["metrics"]["text_accuracy"], 1.0)
        provenance = report["engine_provenance"]
        self.assertEqual(provenance["version"], "tesseract 5.5.0")
        self.assertEqual(provenance["configuration"], {"executable": "tesseract-local", "language": "ita", "oem": "1", "psm": "6", "output": "stdout"})
        self.assertEqual(commands[0], ["tesseract-local", "--version"])
        self.assertEqual(commands[1], ["tesseract-local", str(FIXTURE_DIR / "clean-text.png"), "stdout", "-l", "ita", "--psm", "6", "--oem", "1"])
        self.assertEqual([command["fixture_id"] for command in provenance["commands"][1:]], ["clean-text", "degraded-text", "mixed-table-layout"])

    def test_tesseract_empty_output_is_evaluated_as_empty_text(self) -> None:
        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            stdout = "tesseract 5.5.0\n" if command[-1] == "--version" else ""
            return subprocess.CompletedProcess(command, 0, stdout, "")

        report = run_tesseract_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", command_runner=runner)

        self.assertEqual(report["metrics"]["output_token_count"], 0)
        self.assertEqual(report["metrics"]["reference_token_coverage"], 0.0)

    def test_tesseract_runner_rejects_nonzero_and_missing_executable(self) -> None:
        def failed_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(command, 1, "", "lingua mancante")

        with self.assertRaisesRegex(RuntimeError, "versione.*lingua mancante"):
            run_tesseract_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", command_runner=failed_runner)

        def failed_ocr_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[-1] == "--version":
                return subprocess.CompletedProcess(command, 0, "tesseract 5.5.0\n", "")
            return subprocess.CompletedProcess(command, 1, "", "immagine non leggibile")

        with self.assertRaisesRegex(RuntimeError, "OCR clean-text.*immagine non leggibile"):
            run_tesseract_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", command_runner=failed_ocr_runner)

        def missing_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError(command[0])

        with self.assertRaisesRegex(FileNotFoundError, "Tesseract non trovato: tesseract-local"):
            run_tesseract_ocr_benchmark(
                manifest_path=FIXTURE_DIR / "manifest.json", tesseract_path="tesseract-local", command_runner=missing_runner
            )

    def test_runs_qwen_ollama_fixture_requests_with_provenance(self) -> None:
        calls: list[tuple[str, dict[str, object], float]] = []

        def transport(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
            calls.append((url, payload, timeout))
            if url.endswith("/api/version"):
                return {"version": "0.12.3"}
            if url.endswith("/api/tags"):
                return {"models": [{"name": "qwen3-vl:latest", "digest": "sha256:qwen-test"}]}
            fixture_id = [case["fixture_id"] for case in load_ocr_benchmark_manifest(FIXTURE_DIR / "manifest.json")["cases"]
                          if base64.b64decode(payload["images"][0]) == (FIXTURE_DIR / case["image_file"]).read_bytes()][0]
            return {"response": self._exact_outputs()[fixture_id]}

        report = run_qwen_ollama_ocr_benchmark(
            manifest_path=FIXTURE_DIR / "manifest.json",
            model="qwen3-vl:latest",
            endpoint="http://127.0.0.1:11434/",
            timeout_seconds=30,
            num_ctx=8192,
            num_predict=2048,
            think=False,
            transport=transport,
        )

        self.assertEqual(report["metrics"]["text_accuracy"], 1.0)
        provenance = report["engine_provenance"]
        self.assertEqual(provenance["ollama_version"], "0.12.3")
        self.assertEqual(provenance["model"], {"tag": "qwen3-vl:latest", "digest": "sha256:qwen-test"})
        self.assertEqual(provenance["prompt"]["sha256"], hashlib.sha256(QWEN_OCR_TRANSCRIPTION_PROMPT.encode("utf-8")).hexdigest())
        self.assertEqual(provenance["configuration"]["options"], {"num_ctx": 8192, "num_predict": 2048})
        self.assertEqual([entry["image_sha256"] for entry in provenance["requests"]], [
            self._sha256(FIXTURE_DIR / "clean-text.png"),
            self._sha256(FIXTURE_DIR / "degraded-text.png"),
            self._sha256(FIXTURE_DIR / "mixed-table-layout.png"),
        ])
        self.assertEqual(calls[0], ("http://127.0.0.1:11434/api/version", {}, 30))
        self.assertEqual(calls[1], ("http://127.0.0.1:11434/api/tags", {}, 30))
        request = calls[2][1]
        self.assertEqual(request["model"], "qwen3-vl:latest")
        self.assertEqual(request["prompt"], QWEN_OCR_TRANSCRIPTION_PROMPT)
        self.assertEqual(request["options"], {"num_ctx": 8192, "num_predict": 2048})
        self.assertFalse(request["think"])
        self.assertFalse(request["stream"])
        self.assertEqual(base64.b64decode(request["images"][0]), (FIXTURE_DIR / "clean-text.png").read_bytes())

    def test_qwen_ollama_empty_output_is_evaluated_as_empty_text(self) -> None:
        def transport(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
            if url.endswith("/api/version"):
                return {"version": "0.12.3"}
            if url.endswith("/api/tags"):
                return {"models": [{"name": "qwen3-vl:latest", "digest": "sha256:qwen-test"}]}
            return {"response": ""}

        report = run_qwen_ollama_ocr_benchmark(
            manifest_path=FIXTURE_DIR / "manifest.json", model="qwen3-vl:latest", transport=transport
        )

        self.assertEqual(report["metrics"]["output_token_count"], 0)
        self.assertEqual(report["metrics"]["reference_token_coverage"], 0.0)

    def test_qwen_ollama_rejects_api_errors_missing_model_and_unreachable_service(self) -> None:
        def api_error(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
            if url.endswith("/api/version"):
                return {"version": "0.12.3"}
            if url.endswith("/api/tags"):
                return {"models": [{"name": "qwen3-vl:latest", "digest": "sha256:qwen-test"}]}
            return {"error": "modello non caricato"}

        with self.assertRaisesRegex(RuntimeError, "OCR clean-text.*modello non caricato"):
            run_qwen_ollama_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", model="qwen3-vl:latest", transport=api_error)

        def missing_model(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
            return {"version": "0.12.3"} if url.endswith("/api/version") else {"models": []}

        with self.assertRaisesRegex(ValueError, "Modello Ollama non disponibile"):
            run_qwen_ollama_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", model="qwen3-vl:latest", transport=missing_model)

        def unreachable(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
            raise OSError("connessione rifiutata")

        with self.assertRaisesRegex(RuntimeError, "Ollama non raggiungibile.*connessione rifiutata"):
            run_qwen_ollama_ocr_benchmark(manifest_path=FIXTURE_DIR / "manifest.json", model="qwen3-vl:latest", transport=unreachable)

    def test_qwen_ollama_rejects_remote_or_unsafe_endpoints_before_transport(self) -> None:
        def unexpected_transport(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
            self.fail("Il transport non deve essere chiamato per endpoint non locale.")

        for endpoint in (
            "http://ollama.example:11434",
            "https://ollama.example:11434",
            "http://user:secret@127.0.0.1:11434",
            "http://127.0.0.1:11434?proxy=remote",
            "http://[::1]:11434/#fragment",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(ValueError, "endpoint Ollama"):
                run_qwen_ollama_ocr_benchmark(
                    manifest_path=FIXTURE_DIR / "manifest.json",
                    model="qwen3-vl:latest",
                    endpoint=endpoint,
                    transport=unexpected_transport,
                )

    def _exact_outputs(self) -> dict[str, str]:
        manifest = load_ocr_benchmark_manifest(FIXTURE_DIR / "manifest.json")
        return {
            case["fixture_id"]: (FIXTURE_DIR / case["ground_truth_file"]).read_text(encoding="utf-8")
            for case in manifest["cases"]
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _case(fixture_id: str, ground_truth_file: str, *, image_file: str = "image.png") -> dict[str, object]:
        return {
            "fixture_id": fixture_id,
            "ground_truth_file": ground_truth_file,
            "image_file": image_file,
            "image_format": "png",
            "image_dimensions": {"width": 1, "height": 1},
            "synthetic_transformations": ["uniform white test pixel"],
        }

    @staticmethod
    def _write_png(path: Path, *, filter_byte: int = 0) -> None:
        def chunk(kind: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

        header = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes((filter_byte, 255)))) + chunk(b"IEND", b""))


if __name__ == "__main__":
    unittest.main()
