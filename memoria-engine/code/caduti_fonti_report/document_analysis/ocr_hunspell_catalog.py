"""Local Hunspell resources -> sampled, review-only OcrLanguageLexicon.

Catalog JSON: @type OcrHunspellCatalog, schema_version 1.0, resources containing
@id, language (ita/ita_old/eng/rus/deu), variant, upstream, revision, license,
dic and aff. Paths are relative to the catalog or absolute local paths.
Optional dic_digest/aff_digest pin the expected SHA-256 of the local files.
Metadata is supplied by the resource owner, not an assertion of license review.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
from typing import Any, Protocol


class HunspellLookup(Protocol):
    def lookup(self, word: str) -> bool: ...


BackendFactory = Callable[[Path, Path], HunspellLookup]
_LANGUAGES = {"ita", "ita_old", "eng", "rus", "deu"}


def _required(resource: dict[str, Any], key: str) -> str:
    value = resource.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Campo Hunspell {key} non vuoto richiesto.")
    return value


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _spylls_backend(dic: Path, aff: Path) -> HunspellLookup:
    try:
        from spylls.hunspell import Dictionary
    except ImportError as exc:
        raise ValueError("Backend Hunspell assente: installare l'extra opzionale 'hunspell' (spylls).") from exc
    # Absolute, existing paths prevent spylls' bundled dictionary fallback.
    try:
        return Dictionary.from_files(str(dic.with_suffix("")))
    except Exception as exc:
        raise ValueError(f"Risorsa Hunspell incompatibile con spylls: {dic}") from exc


def build_hunspell_lexicon(
    *, catalog_path: Path, language: str, terms: Iterable[str], variant: str | None = None,
    backend_factory: BackendFactory | None = None, backend_id: str | None = None,
    backend_version: str | None = None,
) -> dict[str, Any]:
    """Check supplied forms including inflections; never expand a dictionary.

Injected backends must supply their ID/version so synthetic tests cannot be
mistaken for a spylls validation. Lookup is performed on the original spelling.
Only sampled accepted forms become entries; unknown tokens remain uncertain.
"""
    if language not in _LANGUAGES:
        raise ValueError("Lingua OCR Hunspell non supportata.")
    if isinstance(terms, (str, bytes)):
        raise ValueError("terms deve contenere stringhe, non essere una stringa.")
    supplied = list(terms)
    if not supplied or any(not isinstance(term, str) or not term.strip() for term in supplied):
        raise ValueError("terms deve contenere stringhe non vuote.")
    catalog_path = catalog_path.resolve()
    catalog_raw = catalog_path.read_bytes()
    catalog = json.loads(catalog_raw.decode("utf-8"))
    if not isinstance(catalog, dict) or catalog.get("@type") != "OcrHunspellCatalog" or catalog.get("schema_version") != "1.0":
        raise ValueError("OcrHunspellCatalog schema_version 1.0 richiesto.")
    resources = catalog.get("resources")
    if not isinstance(resources, list) or not resources:
        raise ValueError("resources Hunspell deve essere una lista non vuota.")
    seen = set()
    matches = []
    for resource in resources:
        if not isinstance(resource, dict):
            raise ValueError("Risorsa catalogo Hunspell non valida.")
        for field in ("@id", "language", "variant", "upstream", "revision", "license", "dic", "aff"):
            _required(resource, field)
        identity = (resource["language"], resource["variant"])
        if resource["language"] not in _LANGUAGES or identity in seen:
            raise ValueError("Lingua/variante catalogo Hunspell non valida o duplicata.")
        seen.add(identity)
        if resource["language"] == language and (variant is None or resource["variant"] == variant):
            matches.append(resource)
    if len(matches) != 1:
        raise ValueError("Risorsa Hunspell mancante o variante ambigua; indicare una variante esplicita.")
    resource = matches[0]
    paths = {kind: (catalog_path.parent / resource[kind]).resolve() for kind in ("dic", "aff")}
    if paths["dic"].suffix != ".dic" or paths["aff"].suffix != ".aff" or paths["dic"].with_suffix("") != paths["aff"].with_suffix(""):
        raise ValueError("Coppia Hunspell .dic/.aff con lo stesso percorso base richiesta.")
    inputs = {}
    for kind, path in paths.items():
        raw = path.read_bytes()
        if not raw:
            raise ValueError(f"Risorsa Hunspell {kind} vuota.")
        digest = _digest(raw)
        if kind + "_digest" in resource and resource[kind + "_digest"] != digest:
            raise ValueError(f"Digest Hunspell {kind} diverso da quello dichiarato.")
        inputs[kind] = {"path": str(path), "digest": digest}
    if backend_factory is None:
        backend_factory = _spylls_backend
        backend_id = "spylls.hunspell"
        backend = backend_factory(paths["dic"], paths["aff"])
        backend_version = version("spylls")
    else:
        if not backend_id or not backend_version:
            raise ValueError("Backend iniettato richiede backend_id e backend_version.")
        backend = backend_factory(paths["dic"], paths["aff"])
    accepted = []
    rejected = []
    for term in sorted(set(supplied)):
        result = backend.lookup(term)
        if not isinstance(result, bool):
            raise ValueError("Il backend Hunspell deve restituire un bool per lookup.")
        (accepted if result else rejected).append(term)
    for kind, path in paths.items():
        if _digest(path.read_bytes()) != inputs[kind]["digest"]:
            raise ValueError("Risorsa Hunspell modificata durante il controllo.")
    if not accepted:
        raise ValueError("Nessun termine riconosciuto; OcrLanguageLexicon richiede entries non vuoto.")
    provenance = {"resource_id": resource["@id"], "language": language, "variant": resource["variant"],
                  "upstream": resource["upstream"], "revision": resource["revision"], "license": resource["license"],
                  "metadata_status": "owner_declared_not_independently_verified", "inputs": inputs,
                  "catalog_path": str(catalog_path), "catalog_digest": _digest(catalog_raw),
                  "backend": {"id": backend_id, "version": backend_version}}
    payload = {"@type": "OcrLanguageLexicon", "schema_version": "1.0", "language": language,
               "version": resource["revision"], "variant": resource["variant"],
               "entries": [{"term": term, "category": "word", "provenance": provenance} for term in accepted],
               "provenance": provenance, "not_found_terms": rejected,
               "lexicon_completeness": "not_asserted", "coverage_scope": "accepted_supplied_forms_only",
               "preview_only": True, "review_status": "unreviewed", "claim_extraction_allowed": False,
               "raw_ocr_unchanged": True}
    payload["@id"] = "ocr-hunspell-lexicon:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return payload


def export_hunspell_lexicon(*, output_path: Path, apply: bool = False, **kwargs: Any) -> dict[str, Any]:
    """Preview by default; explicitly write only a new, idempotent sidecar."""
    payload = build_hunspell_lexicon(**kwargs)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    status = "preview"
    if apply:
        if output_path.exists():
            if output_path.read_text(encoding="utf-8") != encoded:
                raise ValueError(f"Output gia' esistente e diverso: {output_path}")
            status = "skipped_existing"
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
            status = "written"
    return payload | {"operation_status": status, "output_path": str(output_path)}
