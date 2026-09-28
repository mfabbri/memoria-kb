"""Deterministic, review-only ranking of OCR token candidates.

The module never rewrites raw OCR.  Lexicon entries are supplied by the caller
so real dictionaries and their provenance stay outside the engine contract.
"""

from __future__ import annotations

from dataclasses import dataclass
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
