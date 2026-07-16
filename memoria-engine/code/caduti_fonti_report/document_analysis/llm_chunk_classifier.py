from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from ..config import load_nearest_env_file

PROMPT_VERSION = "chunk-classification-v1"
DEFAULT_MODEL_NAME = "fake-local-llm"
DEFAULT_PROVIDER = "fake"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 90
ENV_LLM_CHUNK_PROVIDER = "CADUTI_LLM_CHUNK_PROVIDER"
ENV_LLM_CHUNK_MODEL = "CADUTI_LLM_CHUNK_MODEL"
ENV_LLM_CHUNK_PROMPT_VERSION = "CADUTI_LLM_CHUNK_PROMPT_VERSION"
ENV_LLM_CHUNK_WSL_DISTRIBUTION = "CADUTI_LLM_CHUNK_WSL_DISTRIBUTION"
ENV_LLM_CHUNK_TIMEOUT_SECONDS = "CADUTI_LLM_CHUNK_TIMEOUT_SECONDS"
CHUNK_CLASSIFICATION_RULES_DIR = Path("llm_prompts") / "chunk_classification"
CHUNK_CLASSIFICATION_SCHEMA_NAME = "chunk_classification.schema.json"
CHUNK_CLASSIFICATION_PROMPT_NAME = "chunk_classification.gemma3-4b.prompt.md"
CLASSIFICATION_TYPES = {
    "person_biographical_entry",
    "multi_person_biographical_list",
    "formation_context",
    "battle_context",
    "source_reference_context",
    "bibliography",
    "narrative_context",
    "unclear",
    "manual_review_required",
}
PERSON_PATTERN = re.compile(r"\b[A-Z][a-zA-ZÀ-ÖØ-öø-ÿ'’-]{2,}\s+[A-Z][a-zA-ZÀ-ÖØ-öø-ÿ'’-]{2,}\b")
DATE_PATTERN = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[a-zà-öø-ÿ]+\s+\d{4}|19\d{2})\b", re.IGNORECASE)
PLACE_MARKERS = ("Ca' di Malanca", "Cà di Malanca", "Purocielo", "Monte Colombo", "Cavina", "Brisighella", "Bologna")
FORMATION_MARKERS = ("brigata", "garibaldi", "divisione", "battaglione", "partigian")
BATTLE_MARKERS = ("combatt", "battaglia", "scontro", "tedesch", "mortaio", "spandau", "fucilat", "rastrell")
SOURCE_MARKERS = ("archivio", "fondo", "busta", "fascicolo", "segnatura", "RH ", "fonte", "scheda")
BIBLIOGRAPHY_MARKERS = ("pag.", "pagina", "fonti:", "bibliografia", "nazario galassi", "ferruccio montevecchi")


def chunk_classification_rules_dir(start_path: Path | None = None) -> Path:
    """Resolve LLM chunk-classification contracts from memoria-rules."""
    engine_root = _engine_root(start_path)
    return engine_root.parent / "memoria-rules" / CHUNK_CLASSIFICATION_RULES_DIR


def chunk_classification_schema_path(start_path: Path | None = None) -> Path:
    return chunk_classification_rules_dir(start_path) / CHUNK_CLASSIFICATION_SCHEMA_NAME


def chunk_classification_prompt_path(start_path: Path | None = None) -> Path:
    return chunk_classification_rules_dir(start_path) / CHUNK_CLASSIFICATION_PROMPT_NAME


def llm_chunk_defaults_from_env(start_path: Path | None = None) -> dict[str, Any]:
    load_nearest_env_file(start_path or Path.cwd())
    return {
        "provider": _env_text(ENV_LLM_CHUNK_PROVIDER, DEFAULT_PROVIDER),
        "model_name": _env_text(ENV_LLM_CHUNK_MODEL, DEFAULT_MODEL_NAME),
        "prompt_version": _env_text(ENV_LLM_CHUNK_PROMPT_VERSION, PROMPT_VERSION),
        "wsl_distribution": _env_text(ENV_LLM_CHUNK_WSL_DISTRIBUTION, ""),
        "timeout_seconds": _env_int(ENV_LLM_CHUNK_TIMEOUT_SECONDS, DEFAULT_OLLAMA_TIMEOUT_SECONDS),
    }


def classify_document_chunks(
    *,
    chunk_dir: Path,
    output_dir: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
    prompt_version: str = PROMPT_VERSION,
    provider: str = DEFAULT_PROVIDER,
    wsl_distribution: str = "",
    timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS,
    chunk_paths: list[Path] | None = None,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    paths = sorted(chunk_paths) if chunk_paths is not None else sorted(chunk_dir.rglob("*.chunks.json"))
    for chunk_path in paths:
        payload = _load_json_object(chunk_path)
        skip_reason = _skip_reason(payload=payload)
        if skip_reason:
            skipped.append(_skip_record(payload=payload, chunk_path=chunk_path, reason=skip_reason))
            continue

        classifications = _classifications_for_document(
            payload=payload,
            chunk_path=chunk_path,
            model_name=model_name,
            prompt_version=prompt_version,
            provider=provider,
            wsl_distribution=wsl_distribution,
            timeout_seconds=timeout_seconds,
        )
        document_entry = {
            "@type": "LLMChunkClassificationDocument",
            "source_id": str(payload.get("source_id", "")),
            "source_document_id": str(payload.get("source_document_id", "")),
            "chunk_file": str(chunk_path),
            "review_status": "unreviewed",
            "classification_count": len(classifications),
            "classifications": classifications,
        }
        documents.append(document_entry)
        if output_dir is not None:
            classification_path = output_dir / _classification_relative_path(document_entry)
            classification_path.parent.mkdir(parents=True, exist_ok=True)
            classification_path.write_text(json.dumps(document_entry, ensure_ascii=False, indent=2), encoding="utf-8")

    classification_count = sum(int(document.get("classification_count", 0) or 0) for document in documents)
    result = {
        "@type": "LLMChunkClassificationSet",
        "chunk_dir": str(chunk_dir),
        "output_dir": str(output_dir or ""),
        "classification_method": _classification_method(provider),
        "model_name": model_name,
        "prompt_version": prompt_version,
        "provider": provider,
        "document_count": len(documents),
        "classification_count": classification_count,
        "skipped_count": len(skipped),
        "documents": documents,
        "skipped_documents": skipped,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_llm_chunk_classifications_markdown(result), encoding="utf-8")
    return result


def render_llm_chunk_classifications_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LLMChunkClassification preview",
        "",
        f"- Metodo: `{payload.get('classification_method', '')}`",
        f"- Modello: `{payload.get('model_name', '')}`",
        f"- Prompt: `{payload.get('prompt_version', '')}`",
        f"- Documenti processati: `{payload.get('document_count', 0)}`",
        f"- Classificazioni: `{payload.get('classification_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Classificazioni chunk",
        "",
    ]
    documents = payload.get("documents", [])
    if not isinstance(documents, list) or not documents:
        lines.append("_Nessuna classificazione generata._")
    else:
        for document in documents:
            if not isinstance(document, dict):
                continue
            lines.extend(
                [
                    f"### {document.get('source_document_id', '')}",
                    "",
                    f"- Fonte: `{document.get('source_id', '')}`",
                    f"- Stato revisione: `{document.get('review_status', '')}`",
                    f"- Classificazioni: `{document.get('classification_count', 0)}`",
                    f"- Chunk: `{document.get('chunk_file', '')}`",
                    "",
                ]
            )
            for classification in document.get("classifications", []):
                if not isinstance(classification, dict):
                    continue
                lines.append(
                    f"- `{classification.get('classification_id', '')}` | "
                    f"{classification.get('classification_type', '')} | "
                    f"chunk `{classification.get('chunk_index', '')}` | "
                    f"confidence `{classification.get('confidence', '')}` | "
                    f"uso `{classification.get('recommended_use', '')}`"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _classifications_for_document(
    *,
    payload: dict[str, Any],
    chunk_path: Path,
    model_name: str,
    prompt_version: str,
    provider: str,
    wsl_distribution: str,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    classifications: list[dict[str, Any]] = []
    for chunk in payload.get("chunks", []):
        if not isinstance(chunk, dict):
            continue
        classification = _classification_for_chunk(
            chunk=chunk,
            provider=provider,
            model_name=model_name,
            prompt_version=prompt_version,
            wsl_distribution=wsl_distribution,
            timeout_seconds=timeout_seconds,
        )
        classification_type = _safe_classification_type(str(classification.get("classification_type", "")))
        warnings = _unique_warnings(
            [
                *_string_list(chunk.get("text_quality_warnings", [])),
                *_string_list(classification.get("warnings", [])),
                "llm_output_unreviewed",
            ]
        )
        mentioned_people = _string_list(classification.get("mentioned_people", []))
        mentioned_places = _string_list(classification.get("mentioned_places", []))
        mentioned_dates = _string_list(classification.get("mentioned_dates", []))
        if len(mentioned_people) >= 8 and "many_people_in_chunk" not in warnings:
            warnings.append("many_people_in_chunk")
        if _is_multi_person_chunk(mentioned_people=mentioned_people, classification_type=classification_type):
            classification_type = "multi_person_biographical_list"
            if "multi_person_biographical_list_triage_only" not in warnings:
                warnings.append("multi_person_biographical_list_triage_only")
        if len(mentioned_places) >= 12 and "many_places_in_chunk" not in warnings:
            warnings.append("many_places_in_chunk")
        classification_id = _classification_id(
            source_document_id=str(payload.get("source_document_id", "")),
            chunk_id=str(chunk.get("chunk_id", "")),
            classification_type=classification_type,
        )
        classification_entry = {
                "@type": "LLMChunkClassification",
                "@id": classification_id,
                "classification_id": classification_id,
                "source_id": str(payload.get("source_id", "")),
                "source_document_id": str(payload.get("source_document_id", "")),
                "chunk_file": str(chunk_path),
                "chunk_id": str(chunk.get("chunk_id", "")),
                "chunk_index": int(chunk.get("chunk_index", 0) or 0),
                "classification_type": classification_type,
                "mentioned_people": mentioned_people,
                "mentioned_places": mentioned_places,
                "mentioned_dates": mentioned_dates,
                "confidence": _bounded_confidence(classification.get("confidence", 0.25)),
                "reasons": _string_list(classification.get("reasons", [])),
                "warnings": warnings,
                "recommended_use": _recommended_use(classification_type=classification_type, warnings=warnings),
                "extraction_method": _classification_method(provider),
                "model_name": model_name,
                "prompt_version": prompt_version,
                "provider": provider,
                "input_text_sha256": str(chunk.get("chunk_text_sha256", "")),
                "review_status": "unreviewed",
            }
        diagnostics = classification.get("provider_diagnostics")
        if isinstance(diagnostics, dict):
            classification_entry["provider_diagnostics"] = {
                str(key): str(value) for key, value in diagnostics.items() if str(value).strip()
            }
        classifications.append(classification_entry)
    return classifications


def _classification_for_chunk(
    *,
    chunk: dict[str, Any],
    provider: str,
    model_name: str,
    prompt_version: str,
    wsl_distribution: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    provider = provider.strip().lower() or DEFAULT_PROVIDER
    if provider == "fake":
        return _fake_llm_classification(chunk)
    if provider == "ollama-wsl":
        return _ollama_wsl_classification(
            chunk=chunk,
            model_name=model_name,
            prompt_version=prompt_version,
            wsl_distribution=wsl_distribution,
            timeout_seconds=timeout_seconds,
        )
    return {
        "classification_type": "manual_review_required",
        "mentioned_people": [],
        "mentioned_places": [],
        "mentioned_dates": [],
        "confidence": 0.1,
        "reasons": ["unsupported_llm_provider"],
        "warnings": [f"unsupported_llm_provider:{provider}"],
    }


def _classification_method(provider: str) -> str:
    provider = provider.strip().lower() or DEFAULT_PROVIDER
    if provider == "ollama-wsl":
        return "ollama_wsl_chunk_classification"
    return "fake_local_llm_chunk_classification"


def _engine_root(start_path: Path | None = None) -> Path:
    if start_path is None:
        return Path(__file__).resolve().parents[3]
    current = start_path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if candidate.name == "memoria-engine":
            return candidate
    return Path(__file__).resolve().parents[3]


def _fake_llm_classification(chunk: dict[str, Any]) -> dict[str, Any]:
    text = str(chunk.get("text", ""))
    lower = text.lower()
    reasons: list[str] = []
    warnings: list[str] = []
    classification_type = "narrative_context"
    confidence = 0.44

    if any(marker in lower for marker in SOURCE_MARKERS):
        classification_type = "source_reference_context"
        confidence = 0.66
        reasons.append("source_reference_markers")
    if any(marker in lower for marker in BIBLIOGRAPHY_MARKERS):
        classification_type = "bibliography"
        confidence = 0.64
        reasons.append("bibliography_markers")
    if any(marker in lower for marker in FORMATION_MARKERS):
        classification_type = "formation_context"
        confidence = 0.68
        reasons.append("formation_markers")
    if any(marker in lower for marker in BATTLE_MARKERS):
        classification_type = "battle_context"
        confidence = max(confidence, 0.7)
        reasons.append("battle_or_violence_markers")
    if re.search(r"\b(?:dati|nato|nata|morto|morta|paese di origine|nota biografica)\b", lower) and PERSON_PATTERN.search(text):
        classification_type = "person_biographical_entry"
        confidence = 0.76
        reasons.append("person_biographical_markers")

    mentioned_people = _dedupe(PERSON_PATTERN.findall(text))[:12]
    mentioned_places = [place for place in PLACE_MARKERS if place in text]
    mentioned_dates = _dedupe(DATE_PATTERN.findall(text))[:12]
    if len(mentioned_people) >= 8:
        classification_type = "multi_person_biographical_list"
        confidence = max(confidence, 0.58)
        if "multi_person_biographical_list_signals" not in reasons:
            reasons.append("multi_person_biographical_list_signals")
        warnings.append("many_people_in_chunk")
    if not reasons:
        classification_type = "unclear"
        confidence = 0.28
        reasons.append("no_strong_classification_signal")
        warnings.append("manual_review_recommended")

    return {
        "classification_type": classification_type,
        "mentioned_people": mentioned_people,
        "mentioned_places": mentioned_places,
        "mentioned_dates": mentioned_dates,
        "confidence": confidence,
        "reasons": reasons,
        "warnings": warnings,
    }


def _ollama_wsl_classification(
    *,
    chunk: dict[str, Any],
    model_name: str,
    prompt_version: str,
    wsl_distribution: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    prompt = _ollama_prompt(chunk=chunk, prompt_version=prompt_version)
    request_payload = json.dumps(
        {"model": model_name, "prompt": prompt, "format": "json", "stream": False},
        ensure_ascii=False,
    )
    command = ["wsl"]
    if wsl_distribution.strip():
        command.extend(["-d", wsl_distribution.strip()])
    command.extend(
        [
            "-e",
            "curl",
            "-sS",
            "http://127.0.0.1:11434/api/generate",
            "-H",
            "Content-Type: application/json",
            "--data-binary",
            "@-",
        ]
    )
    try:
        completed = subprocess.run(
            command,
            input=request_payload,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1, int(timeout_seconds)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _manual_review_llm_error(f"ollama_wsl_execution_failed:{type(exc).__name__}")

    if completed.returncode != 0:
        stderr = " ".join(completed.stderr.split())[:180]
        return _manual_review_llm_error(f"ollama_wsl_return_code_{completed.returncode}:{stderr}")

    parsed = _parse_ollama_api_response(completed.stdout)
    if not parsed:
        return _manual_review_llm_error(
            "ollama_wsl_invalid_json",
            diagnostics={"stdout_excerpt": _diagnostic_excerpt(completed.stdout)},
        )
    return parsed


def _parse_ollama_api_response(output: str) -> dict[str, Any]:
    api_payload = _parse_llm_json(output)
    if isinstance(api_payload.get("response"), str):
        parsed_response = _parse_llm_json(str(api_payload["response"]))
        if parsed_response:
            return parsed_response
    return api_payload


def _ollama_prompt(*, chunk: dict[str, Any], prompt_version: str) -> str:
    text = str(chunk.get("text", ""))
    payload = {
        "prompt_version": prompt_version,
        "chunk_id": str(chunk.get("chunk_id", "")),
        "chunk_index": int(chunk.get("chunk_index", 0) or 0),
        "text": text,
    }
    return (
        "Sei un assistente archivistico prudente. Analizza solo il chunk fornito. "
        "Non completare informazioni mancanti. Non produrre claim, fatti verificati, profili o patch. "
        "Restituisci solo JSON valido con questi campi: classification_type, mentioned_people, "
        "mentioned_places, mentioned_dates, confidence, reasons, warnings, recommended_use, review_status. "
        "classification_type deve essere uno tra: person_biographical_entry, multi_person_biographical_list, "
        "formation_context, battle_context, source_reference_context, bibliography, narrative_context, unclear, "
        "manual_review_required. Se il chunk contiene molte persone o piu' schede biografiche, usa "
        "multi_person_biographical_list e triage_only. recommended_use deve essere search_hint, triage_only oppure "
        "manual_review_required. review_status deve essere unreviewed.\n\n"
        f"INPUT:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _parse_llm_json(output: str) -> dict[str, Any]:
    output = _strip_ansi(output).strip()
    if not output:
        return {}
    candidates = [output]
    first = output.find("{")
    last = output.rfind("}")
    if first >= 0 and last > first:
        candidates.append(output[first : last + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str):
            nested = _parse_llm_json(parsed)
            if nested:
                return nested
    return {}


def _manual_review_llm_error(reason: str, diagnostics: dict[str, str] | None = None) -> dict[str, Any]:
    result = {
        "classification_type": "manual_review_required",
        "mentioned_people": [],
        "mentioned_places": [],
        "mentioned_dates": [],
        "confidence": 0.1,
        "reasons": ["llm_provider_error"],
        "warnings": [reason],
    }
    if diagnostics:
        result["provider_diagnostics"] = diagnostics
    return result


def _strip_ansi(value: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)


def _diagnostic_excerpt(value: str, limit: int = 500) -> str:
    clean = _strip_ansi(value).replace("\x00", "").strip()
    clean = " ".join(clean.split())
    return clean[:limit]


def _safe_classification_type(value: str) -> str:
    return value if value in CLASSIFICATION_TYPES else "manual_review_required"


def _is_multi_person_chunk(*, mentioned_people: list[str], classification_type: str) -> bool:
    return len(mentioned_people) >= 8 and classification_type not in {"manual_review_required", "unclear"}


def _recommended_use(*, classification_type: str, warnings: list[str]) -> str:
    if classification_type in {"manual_review_required", "unclear"}:
        return "manual_review_required"
    if classification_type == "multi_person_biographical_list" or "many_people_in_chunk" in warnings:
        return "triage_only"
    return "search_hint"


def _bounded_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.25
    return round(max(0.0, min(parsed, 0.99)), 2)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in {"none", "null", "n/a", "nessuno", "nessuna"}:
            return []
        return [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique_warnings(warnings: list[str]) -> list[str]:
    return _dedupe(warnings)


def _dedupe(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = str(value).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _skip_reason(*, payload: dict[str, Any]) -> str:
    if not payload:
        return "chunk_unreadable"
    if str(payload.get("@type", "")) != "PhysicalDocumentChunkDocument":
        return "unsupported_payload_type"
    chunks = payload.get("chunks", [])
    if not isinstance(chunks, list) or not chunks:
        return "empty_chunks"
    return ""


def _skip_record(*, payload: dict[str, Any], chunk_path: Path, reason: str) -> dict[str, str]:
    return {
        "source_document_id": str(payload.get("source_document_id", "")) if payload else "",
        "chunk_file": str(chunk_path),
        "reason": reason,
    }


def _classification_relative_path(document: dict[str, Any]) -> Path:
    source_id = _safe_path_part(str(document.get("source_id", "")) or "unknown")
    document_id = _safe_path_part(str(document.get("source_document_id", "")) or "unknown")
    return Path(source_id) / f"{document_id}.llm-chunk-classifications.json"


def _classification_id(*, source_document_id: str, chunk_id: str, classification_type: str) -> str:
    digest = hashlib.sha256(f"{source_document_id}|{chunk_id}|{classification_type}".encode("utf-8")).hexdigest()[:16]
    return f"llm-chunk-classification:{digest}"


def _safe_path_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-") or "unknown"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _env_text(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera LLMChunkClassification preview-only da PhysicalDocumentChunk.")
    parser.add_argument("--chunk-dir", default="data/processed/documents")
    parser.add_argument("--output-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/llm_chunk_classifications.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/llm_chunk_classifications.md")
    parser.add_argument("--model-name", default="")
    parser.add_argument("--prompt-version", default="")
    parser.add_argument("--provider", choices=("", "fake", "ollama-wsl"), default="")
    parser.add_argument("--wsl-distribution", default="")
    parser.add_argument("--timeout-seconds", type=int, default=0)
    args = parser.parse_args()
    defaults = llm_chunk_defaults_from_env(Path.cwd())

    payload = classify_document_chunks(
        chunk_dir=Path(args.chunk_dir),
        output_dir=Path(args.output_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        model_name=args.model_name or defaults["model_name"],
        prompt_version=args.prompt_version or defaults["prompt_version"],
        provider=args.provider or defaults["provider"],
        wsl_distribution=args.wsl_distribution or defaults["wsl_distribution"],
        timeout_seconds=args.timeout_seconds or defaults["timeout_seconds"],
    )
    print(f"LLMChunkClassification JSON scritto in {args.output_json}")
    print(f"LLMChunkClassification Markdown scritto in {args.output_md}")
    print(f"Documenti processati: {payload['document_count']}")
    print(f"Classificazioni generate: {payload['classification_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
