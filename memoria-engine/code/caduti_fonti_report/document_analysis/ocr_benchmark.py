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

QWEN_OCR_TRANSCRIPTION_PROMPT = (
    "Trascrivi letteralmente tutto il testo visibile nell'immagine. "
    "Non tradurre, non riassumere, non completare parole mancanti e non aggiungere commenti. "
    "Mantieni l'ordine di lettura piu' naturale possibile. Restituisci solo la trascrizione."
)
_MAX_OLLAMA_IMAGE_BYTES = 20 * 1024 * 1024


def run_qwen_ollama_ocr_benchmark(
    *,
    manifest_path: Path,
    model: str,
    endpoint: str = "http://127.0.0.1:11434",
    timeout_seconds: float = 120.0,
    num_ctx: int = 4096,
    num_predict: int = 4096,
    think: bool = False,
    transport: OllamaTransport | None = None,
) -> dict[str, Any]:
    """Run a local Ollama Qwen transcription benchmark on validated PNG fixtures.

    The adapter is intentionally opt-in and read-only. It transmits only the
    PNG fixtures declared by the synthetic manifest to the configured local
    Ollama endpoint, keeps outputs in memory, and never registers documents or
    writes transcripts.
    """
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Il modello Qwen Ollama deve essere esplicito.")
    root_url = _validated_local_ollama_endpoint(endpoint)
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("timeout_seconds deve essere compreso tra 1 e 600.")
    if not 128 <= num_ctx <= 32768:
        raise ValueError("num_ctx deve essere compreso tra 128 e 32768.")
    if not 1 <= num_predict <= 8192:
        raise ValueError("num_predict deve essere compreso tra 1 e 8192.")
    if not isinstance(think, bool):
        raise ValueError("think deve essere booleano.")

    path = Path(manifest_path)
    manifest = load_ocr_benchmark_manifest(path)
    fixture_dir = path.parent.resolve(strict=True)
    request = transport or _default_ollama_transport
    version_payload = _ollama_request(request, f"{root_url}/api/version", {}, timeout_seconds, "versione")
    version = version_payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("Versione Ollama assente o non valida.")
    tags_payload = _ollama_request(request, f"{root_url}/api/tags", {}, timeout_seconds, "elenco modelli")
    model_digest = _ollama_model_digest(tags_payload, model.strip())

    request_options = {"num_ctx": num_ctx, "num_predict": num_predict}
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
        image_bytes = image_path.read_bytes()
        if len(image_bytes) > _MAX_OLLAMA_IMAGE_BYTES:
            raise ValueError(f"Immagine troppo grande per il benchmark Qwen: {fixture_id}.")
        payload = {
            "model": model.strip(),
            "prompt": QWEN_OCR_TRANSCRIPTION_PROMPT,
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
                "endpoint": "/api/generate",
                "image_sha256": _sha256_file(image_path),
                "latency_ms": latency_ms,
            }
        )

    report = evaluate_ocr_benchmark(manifest_path=path, ocr_outputs=outputs)
    report["engine_provenance"] = {
        "engine": "qwen-ollama",
        "ollama_version": version.strip(),
        "model": {"tag": model.strip(), "digest": model_digest},
        "prompt": {"sha256": hashlib.sha256(QWEN_OCR_TRANSCRIPTION_PROMPT.encode("utf-8")).hexdigest()},
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
    language: str = "ita",
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
        command = _build_tesseract_benchmark_command(
            image_path=image_path,
            tesseract_path=tesseract_path,
            language=language,
            page_segmentation_mode=page_segmentation_mode,
            engine_mode=engine_mode,
        )
        completed = _run_tesseract_benchmark_command(
            command=command, runner=runner, tesseract_path=tesseract_path, purpose=f"OCR {fixture_id}"
        )
        outputs[fixture_id] = completed.stdout or ""
        commands.append({"purpose": "ocr", "fixture_id": fixture_id, "arguments": command})

    report = evaluate_ocr_benchmark(manifest_path=path, ocr_outputs=outputs)
    report["engine_provenance"] = {
        "engine": "tesseract",
        "version": version,
        "configuration": {
            "executable": tesseract_path,
            "language": language.strip(),
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
        if not isinstance(fixture_id, str) or not fixture_id.strip():
            raise ValueError("Ogni fixture benchmark OCR richiede fixture_id.")
        if fixture_id in fixture_ids:
            raise ValueError(f"fixture_id duplicato nel benchmark OCR: {fixture_id}")
        fixture_ids.add(fixture_id)
        if not isinstance(ground_truth_file, str) or not ground_truth_file.strip():
            raise ValueError(f"La fixture {fixture_id} richiede ground_truth_file.")
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
        provenance = {
            "fixture_id": fixture_id,
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
