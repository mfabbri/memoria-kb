"""Page-scoped OCR reference contracts and deterministic offline metrics.

References remain review artifacts.  This module can calculate diagnostic
metrics for synthetic or draft references, but only a verified human reference
whose page identity matches the OCR evidence is eligible for an accuracy claim.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import json
import re
import unicodedata
from typing import Any

from .document_structure import DocumentStructure


_TOKEN_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)
_REFERENCE_ORIGINS = {"synthetic", "human_verified"}
_REVIEW_STATUSES = {"draft", "verified"}
_BLOCK_KINDS = {"heading", "paragraph", "key_value", "list", "table", "unknown"}


@dataclass(frozen=True)
class PageReference:
    """Validated reference text and expected structure for one original page."""

    reference_id: str
    origin: str
    review_status: str
    page_id: str
    source_image_hash: str
    original_page_json: str
    text: str
    blocks: tuple[dict[str, str | None], ...]


def load_page_reference(payload: Mapping[str, Any]) -> PageReference:
    """Validate a serializable reference package without accepting real facts.

    The package identifies the original image, so a crop or enhanced OCR
    transform may be compared while still being anchored to the same page.
    """
    if not isinstance(payload, Mapping) or payload.get("@type") != "OcrPageReference":
        raise ValueError("La reference OCR richiede @type OcrPageReference.")
    reference_id = _required_text(payload.get("reference_id"), "reference_id")
    origin = payload.get("origin")
    if origin not in _REFERENCE_ORIGINS:
        raise ValueError("La reference OCR richiede origin synthetic o human_verified.")
    review_status = payload.get("review_status")
    if review_status not in _REVIEW_STATUSES:
        raise ValueError("La reference OCR richiede review_status draft o verified.")
    page = payload.get("page")
    if not isinstance(page, Mapping):
        raise ValueError("La reference OCR richiede page.")
    page_id = _required_text(page.get("page_id"), "page.page_id")
    image_hash = _required_text(page.get("source_image_hash"), "page.source_image_hash")
    if not re.fullmatch(r"[0-9a-f]{64}", image_hash):
        raise ValueError("page.source_image_hash deve essere SHA-256 esadecimale.")
    original_page = page.get("original_page")
    if not isinstance(original_page, Mapping):
        raise ValueError("La reference OCR richiede page.original_page.")
    _validated_original_page(original_page)
    if original_page["page_id"] != page_id or original_page["source_image_hash"] != image_hash:
        raise ValueError("page.original_page deve corrispondere a page_id e source_image_hash della reference.")
    if origin == "human_verified":
        _verified_audit(payload.get("audit"))
    text = payload.get("text")
    if not isinstance(text, str):
        raise ValueError("La reference OCR richiede text testuale.")
    blocks = _reference_blocks(payload.get("blocks"))
    return PageReference(reference_id, origin, review_status, page_id, image_hash,
                         _canonical_json(original_page), text, tuple(blocks))


def evaluate_page_reference(*, reference: Mapping[str, Any], evidence: Mapping[str, Any],
                            structure: DocumentStructure) -> dict[str, Any]:
    """Compare one OCR variant to one reference and state claim eligibility.

    Results are deterministic and local.  Metrics remain diagnostic whenever
    the reference is synthetic, draft, or bound to another original page.
    """
    expected = load_page_reference(reference)
    if not isinstance(structure, DocumentStructure):
        raise TypeError("La valutazione strutturale richiede DocumentStructure.")
    evidence_identity = _evidence_identity(evidence)
    structure_identity = structure.source_evidence.to_dict()
    identity_checks = {
        "reference_page_id_matches": expected.page_id == evidence_identity["page_id"],
        "reference_source_image_hash_matches": expected.source_image_hash == evidence_identity["source_image_hash"],
        "reference_original_page_matches": expected.original_page_json == evidence_identity["original_page_json"],
        "structure_page_id_matches": structure.page_id == evidence_identity["page_id"],
        "structure_evidence_matches": _same_evidence_identity(structure_identity, evidence_identity),
    }
    identity_matches = all(identity_checks.values())
    output_text = "\n".join(_region_texts(evidence))
    text_metrics = _text_metrics(expected.text, output_text)
    structural_metrics = _structural_metrics(expected.blocks, structure)
    accuracy_eligible = expected.origin == "human_verified" and expected.review_status == "verified" and identity_matches
    reasons: list[str] = []
    if expected.origin != "human_verified":
        reasons.append("reference_origin_is_not_human_verified")
    if expected.review_status != "verified":
        reasons.append("reference_review_is_not_verified")
    if not identity_matches:
        reasons.append("reference_or_structure_page_identity_mismatch")
    return {
        "@type": "OcrPageReferenceEvaluation",
        "schema_version": "1.0",
        "reference": {
            "reference_id": expected.reference_id,
            "origin": expected.origin,
            "review_status": expected.review_status,
            "page_id": expected.page_id,
            "source_image_hash": expected.source_image_hash,
            "original_page": json.loads(expected.original_page_json),
            "audit": reference.get("audit"),
        },
        "evidence": {
            "page_id": evidence_identity["page_id"],
            "source_image_hash": evidence_identity["source_image_hash"],
            "transform_id": evidence_identity["transform_id"],
            "engine": evidence_identity["engine"],
            "language": evidence_identity["language"],
            "model": json.loads(evidence_identity["model_json"]),
            "image_transform": json.loads(evidence_identity["image_transform_json"]),
            "source_page": json.loads(evidence_identity["source_page_json"]),
        },
        "identity_checks": identity_checks,
        "accuracy_eligible": accuracy_eligible,
        "accuracy_ineligibility_reasons": reasons,
        "text_metrics": text_metrics,
        "structural_metrics": structural_metrics,
    }


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"La reference OCR richiede {field} non vuoto.")
    return value.strip()


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("La provenance della reference non e serializzabile.") from exc


def _reference_blocks(value: Any) -> list[dict[str, str | None]]:
    if not isinstance(value, list):
        raise ValueError("La reference OCR richiede blocks come lista.")
    blocks: list[dict[str, str | None]] = []
    for index, block in enumerate(value):
        if not isinstance(block, Mapping) or block.get("kind") not in _BLOCK_KINDS:
            raise ValueError(f"Blocco reference {index} non valido.")
        text = block.get("text")
        if not isinstance(text, str):
            raise ValueError(f"Blocco reference {index} senza text.")
        item: dict[str, str | None] = {"kind": str(block["kind"]), "text": text}
        if block.get("kind") == "key_value":
            value_text = block.get("value")
            if not isinstance(value_text, str):
                raise ValueError(f"Blocco key_value {index} senza value.")
            item["value"] = value_text
        blocks.append(item)
    return blocks


def _verified_audit(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("La reference human_verified richiede audit.")
    _required_text(value.get("reviewer"), "audit.reviewer")
    _required_text(value.get("decision_reference"), "audit.decision_reference")
    verified_at = _required_text(value.get("verified_at"), "audit.verified_at")
    try:
        timestamp = datetime.fromisoformat(f"{verified_at[:-1]}+00:00" if verified_at.endswith("Z") else verified_at)
    except ValueError as exc:
        raise ValueError("audit.verified_at deve essere un timestamp ISO-8601 valido con fuso orario.") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("audit.verified_at deve essere un timestamp ISO-8601 con fuso orario.")


def _evidence_identity(evidence: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(evidence, Mapping) or evidence.get("@type") != "OcrPageEvidence":
        raise ValueError("La valutazione richiede OcrPageEvidence.")
    result = {field: _required_text(evidence.get(field), f"evidence.{field}")
              for field in ("page_id", "source_image_hash", "transform_id", "engine", "language")}
    if not re.fullmatch(r"[0-9a-f]{64}", result["source_image_hash"]):
        raise ValueError("evidence.source_image_hash deve essere SHA-256 esadecimale.")
    source_page = evidence.get("source_page")
    if not isinstance(source_page, Mapping):
        raise ValueError("OcrPageEvidence senza source_page valido.")
    model = evidence.get("model")
    image_transform = evidence.get("image_transform")
    if not isinstance(model, Mapping) or (image_transform is not None and not isinstance(image_transform, Mapping)):
        raise ValueError("OcrPageEvidence senza model o image_transform validi.")
    original_page = _original_page(source_page)
    if original_page["page_id"] != result["page_id"] or original_page["source_image_hash"] != result["source_image_hash"]:
        raise ValueError("source_page.original_page deve corrispondere a page_id e source_image_hash dell'evidenza.")
    result["source_page_json"] = _canonical_json(source_page)
    result["original_page_json"] = _canonical_json(original_page)
    result["model_json"] = _canonical_json(model)
    result["image_transform_json"] = _canonical_json(image_transform or {})
    return result


def _original_page(source_page: Mapping[str, Any]) -> Mapping[str, Any]:
    """Use an explicit original anchor when a variant records crop details."""
    original = source_page.get("original_page")
    if not isinstance(original, Mapping):
        raise ValueError("source_page.original_page deve essere un oggetto.")
    _validated_original_page(original)
    return original


def _validated_original_page(original: Mapping[str, Any]) -> None:
    _required_text(original.get("page_id"), "source_page.original_page.page_id")
    _required_text(original.get("source_file"), "source_page.original_page.source_file")
    dimensions = original.get("source_dimensions")
    if (not isinstance(dimensions, Mapping) or not isinstance(dimensions.get("width"), int)
            or not isinstance(dimensions.get("height"), int) or dimensions["width"] <= 0 or dimensions["height"] <= 0):
        raise ValueError("source_page.original_page.source_dimensions deve avere width e height positive.")
    original_hash = _required_text(original.get("source_image_hash"), "source_page.original_page.source_image_hash")
    if not re.fullmatch(r"[0-9a-f]{64}", original_hash):
        raise ValueError("source_page.original_page.source_image_hash deve essere SHA-256 esadecimale.")


def _same_evidence_identity(structure_identity: Mapping[str, Any], evidence_identity: Mapping[str, str]) -> bool:
    return (structure_identity.get("page_id") == evidence_identity["page_id"]
            and structure_identity.get("source_image_hash") == evidence_identity["source_image_hash"]
            and structure_identity.get("transform_id") == evidence_identity["transform_id"]
            and structure_identity.get("engine") == evidence_identity["engine"]
            and structure_identity.get("language") == evidence_identity["language"]
            and _canonical_json(structure_identity.get("source_page", {})) == evidence_identity["source_page_json"]
            and _canonical_json(structure_identity.get("model", {})) == evidence_identity["model_json"]
            and _canonical_json(structure_identity.get("image_transform") or {}) == evidence_identity["image_transform_json"])


def _region_texts(evidence: Mapping[str, Any]) -> list[str]:
    regions = evidence.get("regions")
    if not isinstance(regions, list):
        raise ValueError("OcrPageEvidence senza regions valida.")
    texts: list[str] = []
    for index, region in enumerate(regions):
        if not isinstance(region, Mapping) or not isinstance(region.get("text"), str):
            raise ValueError(f"Regione OCR {index} senza text valido.")
        texts.append(region["text"])
    return texts


def _normalised_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _tokens(value: str) -> list[str]:
    return _TOKEN_PATTERN.findall(_normalised_text(value))


def _distance(reference: Sequence[str], output: Sequence[str]) -> int:
    previous = list(range(len(output) + 1))
    for row, expected in enumerate(reference, start=1):
        current = [row]
        for column, actual in enumerate(output, start=1):
            current.append(min(current[-1] + 1, previous[column] + 1,
                               previous[column - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def _token_counts(reference: list[str], output: list[str]) -> tuple[int, int, int]:
    """Return matches, omissions and additions from deterministic alignment."""
    rows, columns = len(reference) + 1, len(output) + 1
    matrix = [[0] * columns for _ in range(rows)]
    for row in range(1, rows): matrix[row][0] = row
    for column in range(1, columns): matrix[0][column] = column
    for row in range(1, rows):
        for column in range(1, columns):
            matrix[row][column] = min(matrix[row - 1][column - 1] + (reference[row - 1] != output[column - 1]),
                                      matrix[row - 1][column] + 1, matrix[row][column - 1] + 1)
    matches = omissions = additions = 0
    row, column = len(reference), len(output)
    while row or column:
        if row and column and reference[row - 1] == output[column - 1] and matrix[row][column] == matrix[row - 1][column - 1]:
            matches, row, column = matches + 1, row - 1, column - 1
        elif row and column and matrix[row][column] == matrix[row - 1][column - 1] + 1:
            omissions, additions, row, column = omissions + 1, additions + 1, row - 1, column - 1
        elif row:
            omissions, row = omissions + 1, row - 1
        else:
            additions, column = additions + 1, column - 1
    return matches, omissions, additions


def _text_metrics(reference: str, output: str) -> dict[str, int | float]:
    reference_chars, output_chars = list(_normalised_text(reference)), list(_normalised_text(output))
    reference_tokens, output_tokens = _tokens(reference), _tokens(output)
    matches, omissions, additions = _token_counts(reference_tokens, output_tokens)
    character_error_rate = _distance(reference_chars, output_chars) / len(reference_chars) if reference_chars else float(bool(output_chars))
    word_error_rate = _distance(reference_tokens, output_tokens) / len(reference_tokens) if reference_tokens else float(bool(output_tokens))
    return {"character_error_rate": round(character_error_rate, 6), "word_error_rate": round(word_error_rate, 6),
            "reference_token_count": len(reference_tokens), "output_token_count": len(output_tokens),
            "matched_token_count": matches, "omitted_token_count": omissions, "added_token_count": additions,
            "reference_token_coverage": round(matches / len(reference_tokens), 6) if reference_tokens else float(not output_tokens),
            "invention_rate": round(additions / len(output_tokens), 6) if output_tokens else 0.0}


def _signature(block: Mapping[str, str | None]) -> tuple[str, str, str | None]:
    return (str(block["kind"]), _normalised_text(str(block["text"])),
            _normalised_text(str(block["value"])) if block.get("value") is not None else None)


def _lcs_count(expected: Sequence[tuple[str, str, str | None]], actual: Sequence[tuple[str, str, str | None]]) -> int:
    previous = [0] * (len(actual) + 1)
    for expected_item in expected:
        current = [0]
        for index, actual_item in enumerate(actual, start=1):
            current.append(previous[index - 1] + 1 if expected_item == actual_item else max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def _ratio(numerator: int, denominator: int, empty_match: bool) -> float:
    return round(numerator / denominator, 6) if denominator else float(empty_match)


def _structural_metrics(expected: Sequence[Mapping[str, str | None]], structure: DocumentStructure) -> dict[str, int | float | bool]:
    actual = [{"kind": block.kind, "text": block.text, "value": block.value} for block in structure.blocks]
    expected_signatures = [_signature(block) for block in expected]
    actual_signatures = [_signature(block) for block in actual]
    lcs = _lcs_count(expected_signatures, actual_signatures)
    expected_pairs = Counter((_normalised_text(str(block["text"])), _normalised_text(str(block["value"])))
                             for block in expected if block["kind"] == "key_value")
    actual_pairs = Counter((_normalised_text(str(block["text"])), _normalised_text(str(block["value"])))
                           for block in actual if block["kind"] == "key_value" and block["value"] is not None)
    pair_matches = sum((expected_pairs & actual_pairs).values())
    pair_precision = pair_matches / sum(actual_pairs.values()) if actual_pairs else float(not expected_pairs)
    pair_recall = pair_matches / sum(expected_pairs.values()) if expected_pairs else float(not actual_pairs)
    pair_f1 = 2 * pair_precision * pair_recall / (pair_precision + pair_recall) if pair_precision + pair_recall else 0.0
    expected_kinds, actual_kinds = Counter(block["kind"] for block in expected), Counter(block["kind"] for block in actual)
    kind_matches = sum((expected_kinds & actual_kinds).values())
    return {"reference_block_count": len(expected), "output_block_count": len(actual),
            "reading_order_lcs_count": lcs, "reading_order_precision": _ratio(lcs, len(actual_signatures), not expected_signatures),
            "reading_order_recall": _ratio(lcs, len(expected_signatures), not actual_signatures),
            "block_kind_precision": _ratio(kind_matches, len(actual), not expected),
            "block_kind_recall": _ratio(kind_matches, len(expected), not actual),
            "label_value_pair_precision": round(pair_precision, 6), "label_value_pair_recall": round(pair_recall, 6),
            "label_value_pair_f1": round(pair_f1, 6), "structure_exact_match": expected_signatures == actual_signatures}
