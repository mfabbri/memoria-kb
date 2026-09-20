"""Offline OCR benchmark metrics and an opt-in local Tesseract adapter.

The evaluator accepts OCR output as plain strings and stays engine-independent.
The explicit Tesseract runner invokes the configured local binary on manifest
fixtures, captures stdout, and never registers or writes document transcripts.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import math
import re
import subprocess
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from collections.abc import Callable, Mapping
from pathlib import Path, PureWindowsPath
from typing import Any


NORMALIZATION_ID = "nfkc-casefold-unicode-token-v1"
_TOKEN_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)
TesseractCommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]
OllamaTransport = Callable[[str, Mapping[str, Any], float], Mapping[str, Any]]
PaddleOcrPredictionRunner = Callable[[Path, str], Any]
_PADDLE_OCR_V5_LANGUAGE_CODES = {"ita": "it", "deu": "de", "eng": "en", "rus": "ru"}
_PADDLE_OCR_V5_RECOGNITION_PREFIXES = {
    "ita": "latin_PP-OCRv5_",
    "deu": "latin_PP-OCRv5_",
    "eng": "en_PP-OCRv5_",
    "rus": "eslav_PP-OCRv5_",
}
_PADDLE_OCR_INFERENCE_FILES = ("inference.json", "inference.pdiparams", "inference.yml")

QWEN_OCR_TRANSCRIPTION_PROMPT = (
    "Trascrivi letteralmente tutto il testo visibile nell'immagine. "
    "Non tradurre, non riassumere, non completare parole mancanti e non aggiungere commenti. "
    "Mantieni l'ordine di lettura piu' naturale possibile. Restituisci solo la trascrizione."
)
_MAX_OLLAMA_IMAGE_BYTES = 20 * 1024 * 1024


def _run_ollama_vision_ocr_benchmark(
    *,
    engine: str,
    manifest_path: Path,
    model: str,
    endpoint: str = "http://127.0.0.1:11434",
    timeout_seconds: float = 120.0,
    num_ctx: int = 4096,
    num_predict: int = 4096,
    think: bool = False,
    prompt: str = QWEN_OCR_TRANSCRIPTION_PROMPT,
    language_prompts: Mapping[str, str] | None = None,
    temperature: float = 0.0,
    transport: OllamaTransport | None = None,
) -> dict[str, Any]:
    """Run a local Ollama vision transcription benchmark on validated PNG fixtures.

    The adapter is intentionally opt-in and read-only. It transmits only the
    PNG fixtures declared by the synthetic manifest to the configured local
    Ollama endpoint, keeps outputs in memory, and never registers documents or
    writes transcripts.
    """
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Il modello Ollama vision deve essere esplicito.")
    root_url = _validated_local_ollama_endpoint(endpoint)
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("timeout_seconds deve essere compreso tra 1 e 600.")
    if not 128 <= num_ctx <= 32768:
        raise ValueError("num_ctx deve essere compreso tra 128 e 32768.")
    if not 1 <= num_predict <= 8192:
        raise ValueError("num_predict deve essere compreso tra 1 e 8192.")
    if not isinstance(think, bool):
        raise ValueError("think deve essere booleano.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt deve essere testo non vuoto.")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(temperature):
        raise ValueError("temperature deve essere un numero finito tra 0 e 2.")
    if not 0 <= temperature <= 2:
        raise ValueError("temperature deve essere compresa tra 0 e 2.")

    path = Path(manifest_path)
    manifest = load_ocr_benchmark_manifest(path)
    validated_language_prompts = _validated_ollama_language_prompts(language_prompts, manifest["cases"])
    fixture_dir = path.parent.resolve(strict=True)
    request = transport or _default_ollama_transport
    version_payload = _ollama_request(request, f"{root_url}/api/version", {}, timeout_seconds, "versione")
    version = version_payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Versione Ollama assente o non valida.")
    tags_payload = _ollama_request(request, f"{root_url}/api/tags", {}, timeout_seconds, "elenco modelli")
    model_digest = _ollama_model_digest(tags_payload, model.strip())

    request_options = {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": temperature}
    outputs: dict[str, str] = {}
    requests: list[dict[str, Any]] = []
    for fixture in manifest["cases"]:
        fixture_id = fixture["fixture_id"]
        fixture_language = fixture["language"]
        effective_prompt = validated_language_prompts.get(fixture_language, prompt)
        image_path = _fixture_file_path(
            fixture_dir=fixture_dir,
            fixture_file=fixture["image_file"],
            fixture_id=fixture_id,
            label="Immagine",
        )
        _validate_png_dimensions(image_path, fixture["image_dimensions"], fixture_id)
        image_bytes = image_path.read_bytes()
        if len(image_bytes) > _MAX_OLLAMA_IMAGE_BYTES:
            raise ValueError(f"Immagine troppo grande per il benchmark OCR Ollama vision: {fixture_id}.")
        payload = {
            "model": model.strip(),
            "prompt": effective_prompt,
            "images": [base64.b64encode(image_bytes).decode("ascii")],
            "stream": False,
            "think": think,
            "options": request_options,
        }
        started = time.perf_counter()
        response = _ollama_request(request, f"{root_url}/api/generate", payload, timeout_seconds, f"OCR {fixture_id}")
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        output = response.get("response")
        if not isinstance(output, str):
            raise ValueError(f"Risposta Ollama senza trascrizione testuale per la fixture {fixture_id}.")
        outputs[fixture_id] = output
        requests.append(
            {
                "fixture_id": fixture_id,
                "language": fixture_language,
                "endpoint": "/api/generate",
                "image_sha256": _sha256_file(image_path),
                "prompt": {
                    "text": effective_prompt,
                    "sha256": hashlib.sha256(effective_prompt.encode("utf-8")).hexdigest(),
                },
                "response_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
                "latency_ms": latency_ms,
            }
        )

    report = evaluate_ocr_benchmark(manifest_path=path, ocr_outputs=outputs)
    report["engine_provenance"] = {
        "engine": engine,
        "ollama_version": version.strip(),
        "model": {"tag": model.strip(), "digest": model_digest},
        "prompt": {"text": prompt, "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()},
        "configuration": {
            "endpoint": root_url,
            "api": "/api/generate",
            "timeout_seconds": timeout_seconds,
            "stream": False,
            "think": think,
            "options": request_options,
        },
        "requests": requests,
    }
    return report


def run_ollama_vision_ocr_benchmark(
    *,
    manifest_path: Path,
    model: str,
    endpoint: str = "http://127.0.0.1:11434",
    timeout_seconds: float = 120.0,
    num_ctx: int = 4096,
    num_predict: int = 4096,
    think: bool = False,
    prompt: str = QWEN_OCR_TRANSCRIPTION_PROMPT,
    language_prompts: Mapping[str, str] | None = None,
    temperature: float = 0.0,
    transport: OllamaTransport | None = None,
) -> dict[str, Any]:
    """Run a local Ollama vision transcription benchmark on synthetic fixtures."""
    return _run_ollama_vision_ocr_benchmark(
        engine="ollama-vision",
        manifest_path=manifest_path,
        model=model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        num_ctx=num_ctx,
        num_predict=num_predict,
        think=think,
        prompt=prompt,
        language_prompts=language_prompts,
        temperature=temperature,
        transport=transport,
    )


def run_qwen_ollama_ocr_benchmark(
    *,
    manifest_path: Path,
    model: str,
    endpoint: str = "http://127.0.0.1:11434",
    timeout_seconds: float = 120.0,
    num_ctx: int = 4096,
    num_predict: int = 4096,
    think: bool = False,
    prompt: str = QWEN_OCR_TRANSCRIPTION_PROMPT,
    language_prompts: Mapping[str, str] | None = None,
    temperature: float = 0.0,
    transport: OllamaTransport | None = None,
) -> dict[str, Any]:
    """Run the legacy Qwen-labeled Ollama transcription benchmark."""
    return _run_ollama_vision_ocr_benchmark(
        engine="qwen-ollama",
        manifest_path=manifest_path,
        model=model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        num_ctx=num_ctx,
        num_predict=num_predict,
        think=think,
        prompt=prompt,
        language_prompts=language_prompts,
        temperature=temperature,
        transport=transport,
    )


def _validated_ollama_language_prompts(
    language_prompts: Mapping[str, str] | None, fixtures: list[dict[str, Any]]
) -> dict[str, str]:
    """Validate optional fixture-language prompt overrides before Ollama transport."""
    if language_prompts is None:
        return {}
    if not isinstance(language_prompts, Mapping):
        raise ValueError("language_prompts deve essere una mappa lingua-prompt.")

    fixture_languages = {fixture["language"] for fixture in fixtures}
    validated: dict[str, str] = {}
    for language, language_prompt in language_prompts.items():
        if not isinstance(language, str) or language not in fixture_languages:
            raise ValueError("language_prompts contiene una lingua fixture non supportata.")
        if not isinstance(language_prompt, str) or not language_prompt.strip():
            raise ValueError(f"language_prompts[{language!r}] deve essere testo non vuoto.")
        validated[language] = language_prompt
    return validated


def _validated_local_ollama_endpoint(endpoint: str) -> str:
    """Allow image-bearing Ollama calls only to an explicit loopback endpoint."""
    if not isinstance(endpoint, str):
        raise ValueError("L'endpoint Ollama deve essere una URL locale HTTP(S).")
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("L'endpoint Ollama deve essere una URL locale HTTP(S).")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError("L'endpoint Ollama non ammette credenziali, query o fragment.")
    if parsed.path not in {"", "/"}:
        raise ValueError("L'endpoint Ollama deve indicare solo host e porta locali.")
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("L'endpoint Ollama richiede un host loopback esplicito.")
    if hostname.lower() == "localhost":
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise ValueError("L'endpoint Ollama richiede un host loopback esplicito.")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _ollama_model_digest(tags_payload: Mapping[str, Any], model: str) -> str:
    models = tags_payload.get("models")
    if not isinstance(models, list):
        raise ValueError("Elenco modelli Ollama non valido.")
    for item in models:
        if isinstance(item, Mapping) and item.get("name") == model:
            digest = item.get("digest")
            if isinstance(digest, str) and digest.strip():
                return digest.strip()
            raise ValueError(f"Digest del modello Ollama assente: {model}.")
    raise ValueError(f"Modello Ollama non disponibile: {model}.")


def _ollama_request(
    transport: OllamaTransport, url: str, payload: Mapping[str, Any], timeout_seconds: float, purpose: str
) -> Mapping[str, Any]:
    try:
        response = transport(url, payload, timeout_seconds)
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"Ollama non raggiungibile durante {purpose}: {exc}") from exc
    if not isinstance(response, Mapping):
        raise ValueError(f"Risposta Ollama non valida durante {purpose}.")
    error = response.get("error")
    if isinstance(error, str) and error.strip():
        raise RuntimeError(f"Ollama fallito durante {purpose}: {error.strip()}")
    return response


def _default_ollama_transport(url: str, payload: Mapping[str, Any], timeout_seconds: float) -> Mapping[str, Any]:
    data = None if url.endswith("/api/version") or url.endswith("/api/tags") else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"HTTP {exc.code}{': ' + detail if detail else ''}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Risposta Ollama non JSON.") from exc
    if not isinstance(decoded, Mapping):
        raise ValueError("Risposta Ollama JSON non oggetto.")
    return decoded


def run_tesseract_ocr_benchmark(
    *,
    manifest_path: Path,
    tesseract_path: str = "tesseract",
    language: str | None = "ita",
    page_segmentation_mode: str = "",
    engine_mode: str = "",
    command_runner: TesseractCommandRunner | None = None,
) -> dict[str, Any]:
    """Run Tesseract only on manifest PNG fixtures and evaluate its text output.

    This adapter is intentionally read-only: it invokes Tesseract with
    ``stdout`` output and returns an in-memory benchmark report.  It does not
    use the document OCR runner or register processed documents.
    """
    path = Path(manifest_path)
    manifest = load_ocr_benchmark_manifest(path)
    fixture_dir = path.parent.resolve(strict=True)
    runner = command_runner or _default_tesseract_command_runner

    version_command = [tesseract_path, "--version"]
    version_result = _run_tesseract_benchmark_command(
        command=version_command, runner=runner, tesseract_path=tesseract_path, purpose="versione"
    )
    version = (version_result.stdout or "").strip()
    if not version:
        raise ValueError("Versione Tesseract vuota.")

    commands: list[dict[str, Any]] = [{"purpose": "version", "arguments": version_command}]
    outputs: dict[str, str] = {}
    for fixture in manifest["cases"]:
        fixture_id = fixture["fixture_id"]
        image_path = _fixture_file_path(
            fixture_dir=fixture_dir,
            fixture_file=fixture["image_file"],
            fixture_id=fixture_id,
            label="Immagine",
        )
        _validate_png_dimensions(image_path, fixture["image_dimensions"], fixture_id)
        fixture_language = fixture["language"] if language is None else language
        command = _build_tesseract_benchmark_command(
            image_path=image_path,
            tesseract_path=tesseract_path,
            language=fixture_language,
            page_segmentation_mode=page_segmentation_mode,
            engine_mode=engine_mode,
        )
        completed = _run_tesseract_benchmark_command(
            command=command, runner=runner, tesseract_path=tesseract_path, purpose=f"OCR {fixture_id}"
        )
        outputs[fixture_id] = completed.stdout or ""
        commands.append(
            {"purpose": "ocr", "fixture_id": fixture_id, "language": fixture_language, "arguments": command}
        )

    report = evaluate_ocr_benchmark(manifest_path=path, ocr_outputs=outputs)
    report["engine_provenance"] = {
        "engine": "tesseract",
        "version": version,
        "configuration": {
            "executable": tesseract_path,
            "language": "fixture-specific" if language is None else language.strip(),
            "oem": engine_mode.strip(),
            "psm": page_segmentation_mode.strip(),
            "output": "stdout",
        },
        "commands": commands,
    }
    return report


def _build_tesseract_benchmark_command(
    *, image_path: Path, tesseract_path: str, language: str, page_segmentation_mode: str, engine_mode: str
) -> list[str]:
    command = [tesseract_path, str(image_path), "stdout"]
    if language.strip():
        command.extend(["-l", language.strip()])
    if page_segmentation_mode.strip():
        command.extend(["--psm", page_segmentation_mode.strip()])
    if engine_mode.strip():
        command.extend(["--oem", engine_mode.strip()])
    return command


def _run_tesseract_benchmark_command(
    *, command: list[str], runner: TesseractCommandRunner, tesseract_path: str, purpose: str
) -> subprocess.CompletedProcess[str]:
    try:
        completed = runner(command)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Tesseract non trovato: {tesseract_path}") from exc
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        detail = f": {stderr}" if stderr else "."
        raise RuntimeError(f"Tesseract fallito durante {purpose}{detail}")
    return completed


def _default_tesseract_command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8")


def run_paddle_ocr_v5_benchmark(
    *,
    manifest_path: Path,
    text_detection_model_dir: Path | None = None,
    text_detection_model_name: str | None = None,
    text_recognition_model_dirs: Mapping[str, Path] | None = None,
    text_recognition_model_names: Mapping[str, str] | None = None,
    device: str = "cpu",
    enable_mkldnn: bool = True,
    prediction_runner: PaddleOcrPredictionRunner | None = None,
) -> dict[str, Any]:
    """Benchmark local PP-OCRv5 on synthetic fixtures without writing outputs.

    The default runner only accepts explicit local model directories, so it
    cannot fall back to a remote model download.  ``prediction_runner`` is an
    injectable in-memory seam for callers that already own a local OCR runner;
    it receives both the validated image path and its fixture language.
    """
    if not isinstance(device, str) or not device.strip():
        raise ValueError("device PaddleOCR deve essere una stringa non vuota.")
    if not isinstance(enable_mkldnn, bool):
        raise ValueError("enable_mkldnn PaddleOCR deve essere booleano.")
    path = Path(manifest_path)
    manifest = load_ocr_benchmark_manifest(path)
    fixture_dir = path.parent.resolve(strict=True)
    configurations = _paddle_ocr_v5_configurations(
        fixture_languages={fixture["language"] for fixture in manifest["cases"]},
        device=device,
        enable_mkldnn=enable_mkldnn,
        text_detection_model_dir=text_detection_model_dir,
        text_detection_model_name=text_detection_model_name,
        text_recognition_model_dirs=text_recognition_model_dirs,
        text_recognition_model_names=text_recognition_model_names,
    )
    if prediction_runner is None:
        model_provenance = _verified_paddle_ocr_model_provenance(
            text_detection_model_dir=text_detection_model_dir,
            text_recognition_model_dirs=text_recognition_model_dirs,
            configurations=configurations,
        )
        runner, runtime_provenance = _default_paddle_ocr_prediction_runner(configurations)
        runner_label = "paddleocr-local"
    else:
        model_provenance = {"benchmark_model_verified": False, "reason": "injected_runner"}
        runner = prediction_runner
        runtime_provenance = None
        runner_label = "injected-unverified"

    outputs: dict[str, str] = {}
    requests: list[dict[str, Any]] = []
    for fixture in manifest["cases"]:
        fixture_id = fixture["fixture_id"]
        image_path = _fixture_file_path(
            fixture_dir=fixture_dir,
            fixture_file=fixture["image_file"],
            fixture_id=fixture_id,
            label="Immagine",
        )
        _validate_png_dimensions(image_path, fixture["image_dimensions"], fixture_id)
        fixture_language = fixture["language"]
        configuration = configurations[fixture_language]
        configuration_sha256 = _configuration_sha256(configuration)
        started = time.perf_counter()
        prediction = runner(image_path, fixture_language)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        structured_page = paddle_ocr_v5_structured_evidence(
            prediction,
            page_id=fixture_id,
            source_image_hash=_sha256_file(image_path),
            transform_id="synthetic-manifest-declared-v1",
            engine="paddle-ocr-v5",
            language=fixture_language,
            source_page={
                "fixture_id": fixture_id,
                "image_file": fixture["image_file"],
            },
            model={
                "ocr_version": "PP-OCRv5",
                "text_detection_model_name": configuration.get("text_detection_model_name"),
                "text_recognition_model_name": configuration.get("text_recognition_model_name"),
            },
            image_transform={"synthetic_transformations": fixture["synthetic_transformations"]},
        )
        output = "\n".join(region["text"] for region in structured_page["regions"])
        outputs[fixture_id] = output
        requests.append(
            {
                "fixture_id": fixture_id,
                "language": fixture_language,
                "image_sha256": _sha256_file(image_path),
                "model": {
                    "ocr_version": "PP-OCRv5",
                    "text_detection_model_name": configuration.get("text_detection_model_name"),
                    "text_recognition_model_name": configuration.get("text_recognition_model_name"),
                },
                "configuration_sha256": configuration_sha256,
                "response_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
                "latency_ms": latency_ms,
                "structured_page": structured_page,
            }
        )

    report = evaluate_ocr_benchmark(manifest_path=path, ocr_outputs=outputs)
    report["engine_provenance"] = {
        "engine": "paddle-ocr-v5",
        "benchmark_model_verified": prediction_runner is None,
        "model": model_provenance,
        "configuration_by_fixture_language": configurations,
        "runtime": runtime_provenance,
        "runner": runner_label,
        "requests": requests,
    }
    return report


def _paddle_ocr_v5_configurations(
    *,
    fixture_languages: set[str],
    device: str,
    enable_mkldnn: bool,
    text_detection_model_dir: Path | None,
    text_detection_model_name: str | None,
    text_recognition_model_dirs: Mapping[str, Path] | None,
    text_recognition_model_names: Mapping[str, str] | None,
) -> dict[str, dict[str, Any]]:
    """Build explicit v5-only configurations, one for each fixture language."""
    base_configuration: dict[str, Any] = {
        "ocr_version": "PP-OCRv5",
        "device": device.strip(),
        "enable_mkldnn": enable_mkldnn,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    }
    detection_dir = _validated_paddle_model_directory(text_detection_model_dir, "text_detection_model_dir")
    if detection_dir is None:
        return {language: {**base_configuration, "lang": _PADDLE_OCR_V5_LANGUAGE_CODES[language]} for language in fixture_languages}
    detection_name = _validated_paddle_ocr_v5_model_name(text_detection_model_name, "text_detection_model_name")
    if not isinstance(text_recognition_model_dirs, Mapping) or not isinstance(text_recognition_model_names, Mapping):
        raise ValueError("PaddleOCR locale richiede mappe di directory e nomi recognition per ogni lingua fixture.")
    if set(text_recognition_model_dirs) != fixture_languages or set(text_recognition_model_names) != fixture_languages:
        raise ValueError("Le mappe recognition PaddleOCR devono coprire esattamente le lingue fixture.")
    configurations: dict[str, dict[str, Any]] = {}
    for language in fixture_languages:
        recognition_dir = _validated_paddle_model_directory(
            text_recognition_model_dirs[language], f"text_recognition_model_dirs[{language!r}]"
        )
        assert recognition_dir is not None
        recognition_name = _validated_paddle_ocr_v5_model_name(
            text_recognition_model_names[language], f"text_recognition_model_names[{language!r}]"
        )
        expected_prefix = _PADDLE_OCR_V5_RECOGNITION_PREFIXES[language]
        if not recognition_name.startswith(expected_prefix):
            raise ValueError(
                f"text_recognition_model_names[{language!r}] richiede un modello {expected_prefix}* per la lingua fixture."
            )
        configurations[language] = {
            **base_configuration,
            "lang": _PADDLE_OCR_V5_LANGUAGE_CODES[language],
            "text_detection_model_dir": str(detection_dir),
            "text_detection_model_name": detection_name,
            "text_recognition_model_dir": str(recognition_dir),
            "text_recognition_model_name": recognition_name,
        }
    return configurations


def _validated_paddle_model_directory(model_dir: Path | None, parameter: str) -> Path | None:
    if model_dir is None:
        return None
    path = Path(model_dir).resolve(strict=True)
    if not path.is_dir():
        raise ValueError(f"{parameter} PaddleOCR deve indicare una directory locale.")
    if not any(candidate.is_file() for candidate in path.rglob("*")):
        raise ValueError(f"{parameter} PaddleOCR non contiene file modello locali.")
    missing_files = [filename for filename in _PADDLE_OCR_INFERENCE_FILES if not (path / filename).is_file()]
    if missing_files:
        raise ValueError(
            f"{parameter} PaddleOCR richiede file inference locali mancanti: {', '.join(missing_files)}."
        )
    return path


def _validated_paddle_ocr_v5_model_name(model_name: str | None, parameter: str) -> str:
    if not isinstance(model_name, str) or "PP-OCRv5" not in model_name or not model_name.strip():
        raise ValueError(f"{parameter} deve indicare esplicitamente un modello PP-OCRv5.")
    return model_name.strip()


def _configuration_sha256(configuration: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(configuration, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _verified_paddle_ocr_model_provenance(
    *,
    text_detection_model_dir: Path | None,
    text_recognition_model_dirs: Mapping[str, Path] | None,
    configurations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Manifest every local model file before a PaddleOCR engine is created.

    The local static-inference contract requires ``inference.json``,
    ``inference.pdiparams`` and ``inference.yml`` in each model directory.
    The adapter additionally records every supplied file; PaddleOCR can still
    reject an otherwise incomplete model during engine initialization.
    """
    detection_dir = _validated_paddle_model_directory(text_detection_model_dir, "text_detection_model_dir")
    if detection_dir is None or not isinstance(text_recognition_model_dirs, Mapping):
        raise ValueError("Il runner PaddleOCR locale richiede i pesi locali da verificare.")
    recognition: dict[str, Any] = {}
    for language in sorted(configurations):
        model_dir = _validated_paddle_model_directory(
            text_recognition_model_dirs.get(language), f"text_recognition_model_dirs[{language!r}]"
        )
        if model_dir is None:
            raise ValueError(f"Pesi recognition mancanti per la lingua PaddleOCR {language}.")
        recognition[language] = {
            "model_name": configurations[language]["text_recognition_model_name"],
            "files": _paddle_model_file_manifest(model_dir),
        }
    return {
        "benchmark_model_verified": True,
        "detection": {
            "model_name": next(iter(configurations.values()))["text_detection_model_name"],
            "files": _paddle_model_file_manifest(detection_dir),
        },
        "recognition_by_fixture_language": recognition,
    }


def _paddle_model_file_manifest(model_dir: Path) -> list[dict[str, str | int]]:
    root = model_dir.resolve(strict=True)
    files: list[dict[str, str | int]] = []
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not candidate.is_file():
            continue
        relative_path = candidate.relative_to(root)
        if ".cache" in relative_path.parts:
            continue
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"File modello PaddleOCR fuori dalla directory dichiarata: {candidate}") from exc
        files.append(
            {
                "file": relative_path.as_posix(),
                "sha256": _sha256_file(resolved),
                "bytes": resolved.stat().st_size,
            }
        )
    if not files:
        raise ValueError(f"Directory modello PaddleOCR senza file: {root}")
    return files


def _default_paddle_ocr_prediction_runner(
    configurations: Mapping[str, Mapping[str, Any]]
) -> tuple[PaddleOcrPredictionRunner, dict[str, str]]:
    if any(
        not isinstance(configuration.get("text_detection_model_dir"), str)
        or not isinstance(configuration.get("text_recognition_model_dir"), str)
        for configuration in configurations.values()
    ):
        raise ValueError(
            "Il runner PaddleOCR locale richiede text_detection_model_dir e text_recognition_model_dir "
            "per evitare download di pesi."
        )
    try:
        import paddle
        import paddleocr
        from paddleocr import PaddleOCR
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PaddleOCR non è installato o richiede dipendenze locali mancanti; "
            "usa prediction_runner oppure installa PaddleOCR e PaddlePaddle localmente."
        ) from exc

    engines = {language: PaddleOCR(**dict(configuration)) for language, configuration in configurations.items()}

    def run(image_path: Path, fixture_language: str) -> str:
        engine = engines.get(fixture_language)
        if engine is None:
            raise ValueError(f"Lingua fixture PaddleOCR non configurata: {fixture_language}.")
        return engine.predict(str(image_path))

    return run, {
        "paddleocr_version": str(getattr(paddleocr, "__version__", "unknown")),
        "paddle_version": str(getattr(paddle, "__version__", "unknown")),
    }


def _paddle_ocr_prediction_text(prediction: Any) -> str:
    """Extract recognized text from PaddleOCR 3.x in-memory prediction objects."""
    try:
        results = list(prediction)
    except TypeError as exc:
        raise ValueError("Risposta PaddleOCR non iterabile.") from exc
    texts: list[str] = []
    for result in results:
        payload = result if isinstance(result, Mapping) else getattr(result, "json", None)
        if not isinstance(payload, Mapping):
            raise ValueError("Risposta PaddleOCR senza risultato JSON strutturato.")
        payload = payload.get("res", payload)
        if not isinstance(payload, Mapping):
            raise ValueError("Risposta PaddleOCR con struttura risultato non valida.")
        recognized = payload.get("rec_texts")
        if not isinstance(recognized, list) or not all(isinstance(item, str) for item in recognized):
            raise ValueError("Risposta PaddleOCR senza rec_texts testuali.")
        texts.extend(recognized)
    return "\n".join(texts)


def paddle_ocr_v5_structured_evidence(
    prediction: Any,
    *,
    page_id: str,
    source_image_hash: str,
    transform_id: str,
    engine: str,
    language: str,
    source_page: Mapping[str, Any],
    model: Mapping[str, Any],
    image_transform: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Map a PP-OCRv5 prediction to an engine-neutral, page-scoped evidence record.

    This performs no layout interpretation.  Each recognition index becomes a
    stable region ID and preserves the PP-OCR fields available at that index.
    The string prediction form remains accepted for existing injected benchmark
    runners; it creates one legacy-text region with no invented score or shape.
    """
    page_key = _required_ocr_evidence_text(page_id, "page_id")
    if not isinstance(source_image_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_image_hash):
        raise ValueError("source_image_hash dell'evidenza OCR deve essere uno SHA-256 esadecimale.")
    transform_key = _required_ocr_evidence_text(transform_id, "transform_id")
    engine_key = _required_ocr_evidence_text(engine, "engine")
    language_key = _required_ocr_evidence_text(language, "language")
    if not isinstance(source_page, Mapping) or not isinstance(model, Mapping):
        raise ValueError("source_page e model dell'evidenza OCR devono essere oggetti.")
    if image_transform is not None and not isinstance(image_transform, Mapping):
        raise ValueError("image_transform dell'evidenza OCR deve essere un oggetto.")

    regions: list[dict[str, Any]] = []
    if isinstance(prediction, str):
        regions.append(_ocr_region_evidence(page_key, 0, prediction, None, None, None))
    else:
        for payload in _paddle_ocr_prediction_payloads(prediction):
            texts = payload.get("rec_texts")
            if not isinstance(texts, list) or not all(isinstance(item, str) for item in texts):
                raise ValueError("Risposta PaddleOCR senza rec_texts testuali.")
            scores = _paddle_ocr_optional_region_field(payload, "rec_scores", len(texts))
            polys = _paddle_ocr_optional_region_field(payload, "rec_polys", len(texts))
            boxes = _paddle_ocr_optional_region_field(payload, "rec_boxes", len(texts))
            start_index = len(regions)
            regions.extend(
                _ocr_region_evidence(page_key, start_index + index, text, scores[index] if scores else None,
                    polys[index] if polys else None, boxes[index] if boxes else None)
                for index, text in enumerate(texts)
            )
    return {
        "@type": "OcrPageEvidence",
        "schema_version": "1.0",
        "page_id": page_key,
        "source_image_hash": source_image_hash,
        "transform_id": transform_key,
        "engine": engine_key,
        "language": language_key,
        "source_page": _ocr_json_value(source_page),
        "model": _ocr_json_value(model),
        "image_transform": _ocr_json_value(image_transform) if image_transform is not None else None,
        "regions": regions,
    }


def _required_ocr_evidence_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} dell'evidenza OCR deve essere testo non vuoto.")
    return value.strip()


def _paddle_ocr_prediction_payloads(prediction: Any) -> list[Mapping[str, Any]]:
    try:
        results = list(prediction)
    except TypeError as exc:
        raise ValueError("Risposta PaddleOCR non iterabile.") from exc
    payloads: list[Mapping[str, Any]] = []
    for result in results:
        payload = result if isinstance(result, Mapping) else getattr(result, "json", None)
        if not isinstance(payload, Mapping):
            raise ValueError("Risposta PaddleOCR senza risultato JSON strutturato.")
        payload = payload.get("res", payload)
        if not isinstance(payload, Mapping):
            raise ValueError("Risposta PaddleOCR con struttura risultato non valida.")
        payloads.append(payload)
    return payloads


def _paddle_ocr_optional_region_field(payload: Mapping[str, Any], field: str, count: int) -> list[Any] | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != count:
        raise ValueError(f"Risposta PaddleOCR con {field} non allineato a rec_texts.")
    return value


def _ocr_region_evidence(
    page_id: str, index: int, text: str, score: Any, polygon: Any, box: Any
) -> dict[str, Any]:
    region_id = hashlib.sha256(f"{page_id}\x1f{index}".encode("utf-8")).hexdigest()[:24]
    normalized_polygon = _ocr_json_value(polygon) if polygon is not None else None
    normalized_box = _ocr_json_value(box) if box is not None else None
    region: dict[str, Any] = {
        "region_id": f"ocr-region-{region_id}",
        "text": text,
        "confidence": _ocr_json_value(score) if score is not None else None,
        "geometry": {
            "polygon": normalized_polygon,
            "bbox": normalized_box,
        },
    }
    raw_paddle: dict[str, Any] = {}
    if normalized_polygon is not None:
        raw_paddle["rec_polys"] = normalized_polygon
    if normalized_box is not None:
        raw_paddle["rec_boxes"] = normalized_box
    if raw_paddle:
        region["raw_provenance"] = {"paddle_ocr": raw_paddle}
    return region


def _ocr_json_value(value: Any) -> Any:
    """Convert JSON-like Paddle values without changing list order or keys."""
    if isinstance(value, Mapping):
        return {str(key): _ocr_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_ocr_json_value(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _ocr_json_value(tolist())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError("Risposta PaddleOCR contiene un valore non serializzabile nell'evidenza strutturata.")


def load_ocr_benchmark_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and minimally validate a synthetic benchmark manifest."""
    path = Path(manifest_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest benchmark OCR non valido: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Il manifest benchmark OCR deve essere un oggetto JSON.")
    if payload.get("synthetic") is not True:
        raise ValueError("Il manifest benchmark OCR deve dichiarare fixture sintetiche.")
    if not isinstance(payload.get("dataset_id"), str) or not payload["dataset_id"].strip():
        raise ValueError("Il manifest benchmark OCR richiede dataset_id.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Il manifest benchmark OCR richiede almeno una fixture.")
    fixture_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Ogni fixture benchmark OCR deve essere un oggetto.")
        fixture_id = case.get("fixture_id")
        ground_truth_file = case.get("ground_truth_file")
        language = case.get("language")
        if not isinstance(fixture_id, str) or not fixture_id.strip():
            raise ValueError("Ogni fixture benchmark OCR richiede fixture_id.")
        if fixture_id in fixture_ids:
            raise ValueError(f"fixture_id duplicato nel benchmark OCR: {fixture_id}")
        fixture_ids.add(fixture_id)
        if not isinstance(ground_truth_file, str) or not ground_truth_file.strip():
            raise ValueError(f"La fixture {fixture_id} richiede ground_truth_file.")
        if language is None and payload.get("schema_version") == "1.0":
            language = "ita"
            case["language"] = language
        if not isinstance(language, str) or language not in {"ita", "deu", "eng", "rus"}:
            raise ValueError(f"La fixture {fixture_id} richiede una language OCR supportata.")
        _validate_relative_fixture_file(ground_truth_file, "ground_truth_file", fixture_id)
        image_file = case.get("image_file")
        image_format = case.get("image_format")
        dimensions = case.get("image_dimensions")
        transformations = case.get("synthetic_transformations")
        if not isinstance(image_file, str) or not image_file.strip():
            raise ValueError(f"La fixture {fixture_id} richiede image_file.")
        _validate_relative_fixture_file(image_file, "image_file", fixture_id)
        if image_format != "png":
            raise ValueError(f"La fixture {fixture_id} richiede image_format png.")
        if (
            not isinstance(dimensions, dict)
            or not isinstance(dimensions.get("width"), int)
            or not isinstance(dimensions.get("height"), int)
            or dimensions["width"] <= 0
            or dimensions["height"] <= 0
        ):
            raise ValueError(f"La fixture {fixture_id} richiede image_dimensions positive.")
        if not isinstance(transformations, list) or not all(isinstance(item, str) and item.strip() for item in transformations):
            raise ValueError(f"La fixture {fixture_id} richiede synthetic_transformations documentate.")
    return payload


def evaluate_ocr_benchmark(*, manifest_path: Path, ocr_outputs: Mapping[str, str]) -> dict[str, Any]:
    """Evaluate supplied OCR strings against all references in a manifest.

    ``ocr_outputs`` maps a fixture id to the transcription returned by a
    system under evaluation.  Missing fixtures fail closed so aggregate
    metrics cannot silently represent a partial benchmark.
    """
    path = Path(manifest_path)
    manifest = load_ocr_benchmark_manifest(path)
    fixture_dir = path.parent.resolve(strict=True)
    fixture_ids = {fixture["fixture_id"] for fixture in manifest["cases"]}
    unknown_output_ids = set(ocr_outputs).difference(fixture_ids)
    if unknown_output_ids:
        labels = ", ".join(sorted((str(value) for value in unknown_output_ids)))
        raise ValueError(f"Output OCR per fixture sconosciuta: {labels}.")
    cases: list[dict[str, Any]] = []
    total = _Counts()
    language_totals: dict[str, _Counts] = {}
    fixture_provenance: list[dict[str, str]] = []
    for fixture in manifest["cases"]:
        fixture_id = fixture["fixture_id"]
        if fixture_id not in ocr_outputs:
            raise ValueError(f"Output OCR mancante per la fixture {fixture_id}.")
        output = ocr_outputs[fixture_id]
        if not isinstance(output, str):
            raise ValueError(f"L'output OCR per la fixture {fixture_id} deve essere testo.")
        truth_path = _fixture_file_path(
            fixture_dir=fixture_dir,
            fixture_file=fixture["ground_truth_file"],
            fixture_id=fixture_id,
            label="Ground truth",
        )
        image_path = _fixture_file_path(
            fixture_dir=fixture_dir,
            fixture_file=fixture["image_file"],
            fixture_id=fixture_id,
            label="Immagine",
        )
        _validate_png_dimensions(image_path, fixture["image_dimensions"], fixture_id)
        reference = truth_path.read_text(encoding="utf-8")
        counts = _align_tokens(_tokens(reference), _tokens(output))
        total += counts
        fixture_language = fixture["language"]
        language_total = language_totals.setdefault(fixture_language, _Counts())
        language_total += counts
        provenance = {
            "fixture_id": fixture_id,
            "language": fixture_language,
            "ground_truth_file": fixture["ground_truth_file"],
            "ground_truth_sha256": _sha256_file(truth_path),
            "image_file": fixture["image_file"],
            "image_format": fixture["image_format"],
            "image_dimensions": fixture["image_dimensions"],
            "image_sha256": _sha256_file(image_path),
        }
        fixture_provenance.append(provenance)
        cases.append(
            {
                "fixture_id": fixture_id,
                "category": str(fixture.get("category", "")),
                "language": fixture_language,
                "synthetic": True,
                "provenance": provenance,
                "metrics": _metrics(counts),
            }
        )
    return {
        "@type": "OcrOfflineBenchmarkReport",
        "benchmark_id": manifest["dataset_id"],
        "synthetic_dataset": True,
        "normalization": NORMALIZATION_ID,
        "dataset_provenance": {
            "manifest_file": path.name,
            "manifest_sha256": _sha256_file(path),
            "fixtures": fixture_provenance,
        },
        "cases": cases,
        "metrics": _metrics(total),
        "language_metrics": {
            language: {"fixture_count": sum(case["language"] == language for case in cases), "metrics": _metrics(counts)}
            for language, counts in sorted(language_totals.items())
        },
    }


class _Counts:
    def __init__(self, reference: int = 0, output: int = 0, matches: int = 0, omissions: int = 0, additions: int = 0) -> None:
        self.reference = reference
        self.output = output
        self.matches = matches
        self.omissions = omissions
        self.additions = additions

    def __iadd__(self, other: "_Counts") -> "_Counts":
        self.reference += other.reference
        self.output += other.output
        self.matches += other.matches
        self.omissions += other.omissions
        self.additions += other.additions
        return self


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _TOKEN_PATTERN.findall(normalized)


def _validate_relative_fixture_file(fixture_file: str, field: str, fixture_id: str) -> None:
    fixture_path = Path(fixture_file)
    windows_path = PureWindowsPath(fixture_file)
    if (
        fixture_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in fixture_path.parts
        or ".." in windows_path.parts
    ):
        raise ValueError(f"{field} non sicuro per la fixture {fixture_id}.")


def _fixture_file_path(*, fixture_dir: Path, fixture_file: str, fixture_id: str, label: str) -> Path:
    """Resolve a fixture and reject traversal plus symlink/reparse escapes."""
    candidate = (fixture_dir / fixture_file).resolve(strict=True)
    try:
        candidate.relative_to(fixture_dir)
    except ValueError as exc:
        raise ValueError(f"{label} fuori dalla directory fixture per {fixture_id}.") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"{label} benchmark OCR non trovata: {candidate}")
    return candidate


def _validate_png_dimensions(image_path: Path, expected: Mapping[str, int], fixture_id: str) -> None:
    """Validate complete non-interlaced PNG integrity without an image library."""
    data = image_path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Immagine raster non valida per la fixture {fixture_id}: atteso PNG.")

    position = 8
    seen_ihdr = seen_idat = seen_iend = False
    ended_idat = False
    width = height = bit_depth = color_type = None
    idat_parts: list[bytes] = []
    while position < len(data):
        if position + 12 > len(data):
            raise ValueError(f"PNG troncato per la fixture {fixture_id}.")
        length = int.from_bytes(data[position:position + 4], "big")
        chunk_type = data[position + 4:position + 8]
        chunk_end = position + 12 + length
        if chunk_end > len(data):
            raise ValueError(f"PNG troncato per la fixture {fixture_id}.")
        chunk_data = data[position + 8:position + 8 + length]
        supplied_crc = int.from_bytes(data[position + 8 + length:chunk_end], "big")
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != supplied_crc:
            raise ValueError(f"CRC PNG non valido per la fixture {fixture_id}.")
        if not seen_ihdr:
            if chunk_type != b"IHDR" or length != 13:
                raise ValueError(f"PNG senza IHDR valido per la fixture {fixture_id}.")
            width = int.from_bytes(chunk_data[:4], "big")
            height = int.from_bytes(chunk_data[4:8], "big")
            bit_depth, color_type, compression, filter_method, interlace = chunk_data[8:]
            if (
                width <= 0
                or height <= 0
                or compression != 0
                or filter_method != 0
                or interlace != 0
                or (color_type, bit_depth) not in {(0, 1), (0, 2), (0, 4), (0, 8), (0, 16), (2, 8), (2, 16), (3, 1), (3, 2), (3, 4), (3, 8), (4, 8), (4, 16), (6, 8), (6, 16)}
            ):
                raise ValueError(f"IHDR PNG non supportato per la fixture {fixture_id}.")
            seen_ihdr = True
        elif chunk_type == b"IHDR":
            raise ValueError(f"PNG con IHDR duplicato per la fixture {fixture_id}.")
        elif chunk_type == b"IDAT":
            if ended_idat:
                raise ValueError(f"PNG con IDAT non contigui per la fixture {fixture_id}.")
            seen_idat = True
            idat_parts.append(chunk_data)
        elif seen_idat:
            ended_idat = True
        if chunk_type == b"IEND":
            if length != 0 or not seen_idat or chunk_end != len(data):
                raise ValueError(f"PNG senza IEND valido per la fixture {fixture_id}.")
            seen_iend = True
            break
        position = chunk_end

    if not seen_ihdr or not seen_idat or not seen_iend:
        raise ValueError(f"PNG incompleto per la fixture {fixture_id}.")
    assert width is not None and height is not None and bit_depth is not None and color_type is not None
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * bit_depth + 7) // 8
    decompressor = zlib.decompressobj()
    try:
        decoded = decompressor.decompress(b"".join(idat_parts)) + decompressor.flush()
    except zlib.error as exc:
        raise ValueError(f"IDAT PNG non decompressibile per la fixture {fixture_id}.") from exc
    if not decompressor.eof or decompressor.unused_data or len(decoded) != height * (row_bytes + 1):
        raise ValueError(f"IDAT PNG non coerente per la fixture {fixture_id}.")
    if any(decoded[index] > 4 for index in range(0, len(decoded), row_bytes + 1)):
        raise ValueError(f"Filtro PNG non valido per la fixture {fixture_id}.")
    if (width, height) != (expected["width"], expected["height"]):
        raise ValueError(f"Dimensioni raster non coerenti per la fixture {fixture_id}.")


def _align_tokens(reference: list[str], output: list[str]) -> _Counts:
    """Return exact-token alignment counts, treating substitutions as both sides."""
    rows = len(reference) + 1
    columns = len(output) + 1
    matrix = [[0] * columns for _ in range(rows)]
    for row in range(1, rows):
        matrix[row][0] = row
    for column in range(1, columns):
        matrix[0][column] = column
    for row in range(1, rows):
        for column in range(1, columns):
            substitution = matrix[row - 1][column - 1] + (reference[row - 1] != output[column - 1])
            matrix[row][column] = min(substitution, matrix[row - 1][column] + 1, matrix[row][column - 1] + 1)

    matches = omissions = additions = 0
    row, column = len(reference), len(output)
    while row or column:
        if row and column and reference[row - 1] == output[column - 1] and matrix[row][column] == matrix[row - 1][column - 1]:
            matches += 1
            row -= 1
            column -= 1
        elif row and column and matrix[row][column] == matrix[row - 1][column - 1] + 1:
            omissions += 1
            additions += 1
            row -= 1
            column -= 1
        elif row and matrix[row][column] == matrix[row - 1][column] + 1:
            omissions += 1
            row -= 1
        else:
            additions += 1
            column -= 1
    return _Counts(len(reference), len(output), matches, omissions, additions)


def _metrics(counts: _Counts) -> dict[str, int | float]:
    """Compute text-only metrics.

    ``reference_token_coverage`` is the share of reference tokens aligned
    exactly. ``output_length_completeness`` only compares output length to the
    reference length (capped at 1), so it remains distinct from accuracy and
    coverage. The mixed-table fixture therefore measures textual recovery;
    page geometry, cells and reading order are deliberately out of scope.
    """
    reference = counts.reference
    output = counts.output
    denominator = max(reference, output)
    return {
        "reference_token_count": reference,
        "output_token_count": output,
        "matched_token_count": counts.matches,
        "omitted_token_count": counts.omissions,
        "added_token_count": counts.additions,
        "text_accuracy": _exactness_ratio(counts.matches, denominator),
        "reference_token_coverage": _reference_ratio(counts.matches, reference, output),
        "output_length_completeness": _length_completeness(output, reference),
        "invention_rate": _output_ratio(counts.additions, output),
    }


def _exactness_ratio(matches: int, denominator: int) -> float:
    return round(matches / denominator, 6) if denominator else 1.0


def _reference_ratio(matches: int, reference: int, output: int) -> float:
    if reference:
        return round(matches / reference, 6)
    return 1.0 if output == 0 else 0.0


def _length_completeness(output: int, reference: int) -> float:
    if reference:
        return round(min(output / reference, 1.0), 6)
    return 1.0 if output == 0 else 0.0


def _output_ratio(additions: int, output: int) -> float:
    return round(additions / output, 6) if output else 0.0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
