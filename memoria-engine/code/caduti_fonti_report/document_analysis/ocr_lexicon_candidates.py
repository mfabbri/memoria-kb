"""Deterministic, review-only ranking of OCR token candidates.

The module never rewrites raw OCR.  Lexicon entries are supplied by the caller
so real dictionaries and their provenance stay outside the engine contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any


_TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", flags=re.UNICODE)
NORMALIZATION_ID = "nfkc-casefold-lexicon-token-v1"


@dataclass(frozen=True)
class LexiconEntry:
    term: str
    category: str
    source_id: str
    version: str

    def __post_init__(self) -> None:
        for field in ("term", "category", "source_id", "version"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"La voce lessicale richiede {field} non vuoto.")


def rank_ocr_candidates(
    raw_text: str,
    lexicon: Iterable[LexiconEntry],
    *,
    source_document_id: str,
    source_region_id: str,
    max_distance: int = 2,
    max_suggestions: int = 5,
) -> dict[str, Any]:
    """Return provenance-preserving suggestions without changing ``raw_text``."""
    if not isinstance(raw_text, str):
        raise TypeError("raw_text deve essere una stringa.")
    for value, field in ((source_document_id, "source_document_id"), (source_region_id, "source_region_id")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} deve essere non vuoto.")
    if not isinstance(max_distance, int) or isinstance(max_distance, bool) or max_distance < 0:
        raise ValueError("max_distance deve essere un intero non negativo.")
    if not isinstance(max_suggestions, int) or isinstance(max_suggestions, bool) or max_suggestions < 1:
        raise ValueError("max_suggestions deve essere un intero positivo.")

    entries = tuple(lexicon)
    if any(not isinstance(entry, LexiconEntry) for entry in entries):
        raise TypeError("lexicon deve contenere solo LexiconEntry.")
    tokens = []
    for match in _TOKEN_PATTERN.finditer(raw_text):
        raw_token = match.group(0)
        suggestions = []
        for entry in entries:
            distance = _levenshtein(_normalise(raw_token), _normalise(entry.term))
            if distance <= max_distance:
                denominator = max(len(_normalise(raw_token)), len(_normalise(entry.term)), 1)
                suggestions.append({
                    "term": entry.term,
                    "category": entry.category,
                    "source_id": entry.source_id,
                    "version": entry.version,
                    "edit_distance": distance,
                    "score": round(1 - distance / denominator, 6),
                    "score_kind": "lexicon_similarity_not_ocr_confidence",
                })
        suggestions.sort(key=lambda item: (item["edit_distance"], -item["score"], item["term"], item["source_id"]))
        tokens.append({
            "raw_token": raw_token,
            "start": match.start(),
            "end": match.end(),
            "suggestions": suggestions[:max_suggestions],
        })
    return {
        "@type": "OcrLexiconCandidateSet",
        "schema_version": "1.0",
        "normalization_id": NORMALIZATION_ID,
        "source_document_id": source_document_id,
        "source_region_id": source_region_id,
        "raw_text": raw_text,
        "raw_ocr_unchanged": True,
        "review_status": "unreviewed",
        "max_distance": max_distance,
        "max_suggestions": max_suggestions,
        "tokens": tokens,
    }


def _normalise(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _levenshtein(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            current.append(min(current[-1] + 1, previous[column] + 1,
                               previous[column - 1] + (left_char != right_char)))
        previous = current
    return previous[-1]


_REVIEW_TOKEN_PATTERN = re.compile(r"(?:[^\W_\d][^\W_]*(?:[-'][^\W_]+)*(?:\.[^\W_]+)*|\d+)\.?", re.UNICODE)


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Campo {field} non vuoto richiesto.")
    return value


def _load_review_resource(path: Path, expected_type: str) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("@type") != expected_type:
        raise ValueError(f"Risorsa {expected_type} richiesta: {path}")
    return payload, "sha256:" + hashlib.sha256(raw).hexdigest()


def _review_entries(payload: dict[str, Any], *, glossary: bool) -> list[LexiconEntry]:
    source_id = _required_string(payload, "@id")
    version = _required_string(payload, "version")
    if not glossary:
        if payload.get("schema_version") != "1.0":
            raise ValueError("Schema OcrLanguageLexicon non supportato.")
        _required_string(payload, "language")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("entries deve essere una lista non vuota.")
    entries = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("Voce lessicale non valida.")
        term = _required_string(raw, "term")
        if not glossary:
            if raw.get("category") != "word":
                raise ValueError("OcrLanguageLexicon richiede category=word.")
            entries.append(LexiconEntry(term, "word", source_id, version))
            continue
        entry_id = _required_string(raw, "@id")
        entries.append(LexiconEntry(term, "word", entry_id, version))
        for field, category in (("aliases", "word"), ("abbreviations", "abbreviation")):
            values = raw.get(field, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f"Campo glossario {field} non valido.")
            entries.extend(LexiconEntry(value, category, entry_id, version) for value in values)
    return entries


def _review_blocks(structure: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if structure.get("schema_version") != "1.0":
        raise ValueError("Schema DocumentStructure non supportato.")
    if "blocks" in structure:
        pages = [structure]
    else:
        pages = structure.get("pages")
        if not isinstance(pages, list) or not pages:
            raise ValueError("DocumentStructure richiede blocks o pages non vuoti.")
    result = []
    seen = set()
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("blocks"), list):
            raise ValueError("Blocchi struttura non validi.")
        page_id = page.get("page_id", structure.get("page_id"))
        if not isinstance(page_id, str) or not page_id.strip():
            raise ValueError("page_id richiesto per ogni pagina.")
        for block in page["blocks"]:
            if not isinstance(block, dict):
                raise ValueError("Blocco struttura non valido.")
            block_id = block.get("block_id", block.get("id"))
            regions = block.get("source_region_ids")
            if not isinstance(block_id, str) or not block_id.strip() or (page_id, block_id) in seen:
                raise ValueError("ID blocco mancante o duplicato nella pagina.")
            if not isinstance(block.get("text"), str):
                raise ValueError("text deve essere una stringa.")
            if not isinstance(regions, list) or not regions or any(not isinstance(r, str) or not r.strip() for r in regions):
                raise ValueError("source_region_ids non vuoti richiesti.")
            seen.add((page_id, block_id))
            result.append((page_id, block | {"block_id": block_id}))
    return result


def _entry_suggestion(entry: LexiconEntry, distance: int, token: str) -> dict[str, Any]:
    return {"term": entry.term, "category": entry.category, "source_id": entry.source_id,
            "version": entry.version, "edit_distance": distance,
            "score": round(1 - distance / max(len(_normalise(token)), len(_normalise(entry.term)), 1), 6),
            "score_kind": "lexicon_similarity_not_ocr_confidence"}


def build_document_lexicon_review(
    *, structure_path: Path, lexicon_path: Path, output_path: Path,
    glossary_path: Path | None = None, apply: bool = False,
    max_distance: int = 2, max_suggestions: int = 5,
) -> dict[str, Any]:
    """Create an uncertain, review-only diagnostic from explicit offline resources.

    Language lexica use @type OcrLanguageLexicon, schema_version 1.0, @id,
    version, language and entries of {term, category: word}. Coverage is limited
    to those entries; not_found never asserts that a token is a language error.
    """
    # Reuse the ranker's parameter contract even for empty document blocks.
    rank_ocr_candidates("", [], source_document_id="validation", source_region_id="validation",
                        max_distance=max_distance, max_suggestions=max_suggestions)
    structure, structure_digest = _load_review_resource(structure_path, "DocumentStructure")
    lexicon, lexicon_digest = _load_review_resource(lexicon_path, "OcrLanguageLexicon")
    entries = _review_entries(lexicon, glossary=False)
    evidence = structure.get("source_evidence", {})
    if not isinstance(evidence, dict):
        raise ValueError("source_evidence deve essere un oggetto.")
    language = structure.get("language", evidence.get("language"))
    if not isinstance(language, str) or not language.strip():
        raise ValueError("Lingua della struttura richiesta in language o source_evidence.language.")
    aliases = {"deu": "de", "ger": "de", "ita": "it", "eng": "en", "fra": "fr", "fre": "fr"}
    if aliases.get(language, language) != aliases.get(lexicon["language"], lexicon["language"]):
        raise ValueError("Lingua del lessico diversa dalla lingua della struttura.")
    resources = [{"kind": "language_lexicon", "path": str(lexicon_path), "resource_id": lexicon["@id"],
                  "version": lexicon["version"], "digest": lexicon_digest, "language": lexicon["language"]}]
    if glossary_path is not None:
        glossary, digest = _load_review_resource(glossary_path, "MilitaryGlossary")
        entries.extend(_review_entries(glossary, glossary=True))
        resources.append({"kind": "military_glossary", "path": str(glossary_path),
                          "resource_id": glossary["@id"], "version": glossary["version"], "digest": digest,
                          "entry_provenance": [{"entry_id": raw["@id"],
                              "source_reference": raw.get("source_reference", ""),
                              "source_references": raw.get("source_references", [])} for raw in glossary["entries"]]})
    entries = sorted(set(entries), key=lambda e: (e.term, e.category, e.source_id, e.version))
    exact_index: dict[str, list[LexiconEntry]] = {}
    fuzzy_buckets: dict[tuple[str, int], list[tuple[LexiconEntry, str]]] = {}
    declared_spans = []
    for entry in entries:
        normal_term = _normalise(entry.term)
        exact_index.setdefault(normal_term, []).append(entry)
        fuzzy_term = normal_term.rstrip(".")
        fuzzy_buckets.setdefault((entry.category, len(fuzzy_term)), []).append((entry, fuzzy_term))
        # Ordinary words are found by token lookup. Only terms crossing token
        # boundaries need a whole-text pattern (multiword terms and sigla).
        if entry.category == "abbreviation" or any(c.isspace() for c in entry.term) or "." in entry.term:
            pattern = re.compile(r"(?<!\w)(?<![^\W_\d]\.)" + re.escape(entry.term).replace(r"\ ", r"\s+")
                                 + r"(?!\w)(?!\.\w)", re.IGNORECASE)
            declared_spans.append((entry, pattern))
    declared_spans.sort(key=lambda item: (-len(item[0].term), item[0].term, item[0].source_id))
    blocks = []
    counts = {"exact_match": 0, "not_found": 0, "with_fuzzy_suggestions": 0, "non_word": 0}
    for page_id, block in _review_blocks(structure):
        text = block["text"]
        # Match declared terms first, preserving multiword and dotted sigla.
        occupied = []
        spans = []
        for entry, pattern in declared_spans:
            for match in pattern.finditer(text):
                span = (match.start(), match.end())
                if any(span[0] < end and start < span[1] for start, end in occupied):
                    continue
                spans.append(span)
                occupied.append(span)
        cursor = 0
        for start, end in sorted(occupied) + [(len(text), len(text))]:
            spans.extend((cursor + m.start(), cursor + m.end())
                         for m in _REVIEW_TOKEN_PATTERN.finditer(text[cursor:start]))
            cursor = end
        tokens = []
        for start, end in sorted(spans):
            raw_token = text[start:end]
            normal = _normalise(raw_token)
            exact_entries = exact_index.get(normal, [])
            lookup = raw_token if exact_entries else raw_token.rstrip(".")
            if not exact_entries:
                exact_entries = exact_index.get(_normalise(lookup), [])
            letters = "".join(c for c in raw_token if c.isalpha())
            if not letters:
                kind = "non_word"
            elif exact_entries:
                kind = "abbreviation" if any(e.category == "abbreviation" for e in exact_entries) else "word"
            elif "." in raw_token.rstrip(".") or len(letters) > 1 and letters.isupper():
                kind = "abbreviation"
            elif raw_token.endswith(".") and raw_token[0].isupper() and len(letters) <= 5:
                kind = "word_or_abbreviation"
            else:
                kind = "word"
            suggestions = []
            if letters and not exact_entries:
                lookup_normal = _normalise(lookup)
                categories = ("word", "abbreviation") if kind == "word_or_abbreviation" else (kind,)
                for category in categories:
                    for length in range(max(0, len(lookup_normal) - max_distance), len(lookup_normal) + max_distance + 1):
                        for entry, fuzzy_term in fuzzy_buckets.get((category, length), []):
                            distance = _levenshtein(lookup_normal, fuzzy_term)
                            if distance <= max_distance:
                                suggestions.append(_entry_suggestion(entry, distance, lookup))
                suggestions.sort(key=lambda s: (s["edit_distance"], -s["score"], s["term"], s["source_id"], s["version"]))
            status = "non_word" if not letters else "exact_match" if exact_entries else "not_found"
            counts[status] += 1
            counts["with_fuzzy_suggestions"] += bool(suggestions)
            tokens.append({"raw_token": raw_token, "start": start, "end": end, "token_kind": kind,
                           "classification_method": "declared_match_or_abbreviation_shape_heuristic",
                           "status": status, "uncertain": status == "not_found",
                           "needs_human_review": status == "not_found",
                           "exact_matches": [_entry_suggestion(e, 0, lookup) for e in exact_entries],
                           "fuzzy_suggestions": suggestions[:max_suggestions]})
        blocks.append({"page_id": page_id, "block_id": block["block_id"], "text": text,
                       "source_region_ids": block["source_region_ids"], "tokens": tokens})
    payload = {"@type": "OcrDocumentLexiconReview", "schema_version": "1.0",
               "normalization_id": NORMALIZATION_ID, "source_structure": str(structure_path),
               "source_structure_digest": structure_digest, "source_structure_schema_version": structure["schema_version"],
               "source_document_id": structure.get("source_document_id", structure.get("page_id", "")),
               "source_evidence": structure.get("source_evidence", {}), "resources": resources,
               "language": language, "lexicon_completeness": "not_asserted",
               "abbreviation_check": "run_with_explicit_glossary" if glossary_path is not None else "not_run",
               "preview_only": True, "review_status": "unreviewed", "raw_ocr_unchanged": True,
               "claim_extraction_allowed": False, "max_distance": max_distance, "max_suggestions": max_suggestions,
               "coverage_notice": "explicit_resources_only; not_found_is_uncertain_not_a_confirmed_language_error",
               "counts": counts, "blocks": blocks}
    payload["@id"] = "ocr-lexicon-review:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    status = "preview"
    if apply:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
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
