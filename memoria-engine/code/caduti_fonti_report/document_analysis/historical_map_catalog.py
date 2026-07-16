from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .input_processing_plan import MAP_TERMS, build_input_processing_plan


def build_historical_map_catalog(
    *,
    root_dir: Path | None = None,
    input_plan_json: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    plan = _load_or_build_plan(root_dir=root_dir, input_plan_json=input_plan_json)
    maps = [_map_candidate(asset) for asset in plan.get("assets", []) if _is_map_asset(asset)]
    result = {
        "@type": "HistoricalMapCatalog",
        "root_dir": str(plan.get("root_dir", "")),
        "map_candidate_count": len(maps),
        "review_status": "unreviewed",
        "maps": maps,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_historical_map_catalog_markdown(result), encoding="utf-8")
    return result


def render_historical_map_catalog_markdown(catalog: dict[str, Any]) -> str:
    lines = [
        "# Historical map catalog",
        "",
        f"- Root: `{catalog.get('root_dir', '')}`",
        f"- Mappe candidate: `{catalog.get('map_candidate_count', 0)}`",
        f"- Stato revisione: `{catalog.get('review_status', '')}`",
        "",
        "## Mappe candidate",
        "",
    ]
    maps = catalog.get("maps", [])
    if not isinstance(maps, list) or not maps:
        lines.append("_Nessuna mappa candidata trovata._")
    else:
        for item in maps:
            if not isinstance(item, dict):
                continue
            lines.extend(
                [
                    f"### {item.get('title', '') or item.get('raw_file', '') or item.get('source_document_id', '')}",
                    "",
                    f"- Raw file: `{item.get('raw_file', '')}`",
                    f"- Sidecar: `{item.get('sidecar_file', '')}`",
                    f"- Media type: `{item.get('media_type', '')}`",
                    f"- SHA256: `{item.get('sha256', '')}`",
                    f"- OCR mappa: `{item.get('map_ocr_status', '')}`",
                    f"- Georeferenziazione: `{item.get('georeferencing_status', '')}`",
                    f"- Revisione: `{item.get('review_status', '')}`",
                ]
            )
            terms = item.get("map_signal_terms", [])
            if isinstance(terms, list) and terms:
                lines.append(f"- Segnali: {', '.join(f'`{term}`' for term in terms)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_or_build_plan(*, root_dir: Path | None, input_plan_json: Path | None) -> dict[str, Any]:
    if input_plan_json is not None and input_plan_json.exists():
        payload = json.loads(input_plan_json.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    if root_dir is None:
        raise ValueError("root_dir or input_plan_json is required")
    return build_input_processing_plan(root_dir=root_dir)


def _is_map_asset(asset: Any) -> bool:
    if not isinstance(asset, dict):
        return False
    return (
        str(asset.get("document_class_guess", "")) == "historical_map"
        or str(asset.get("recommended_action", "")) == "historical_map_georeferencing_required"
    )


def _map_candidate(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": "HistoricalMapCandidate",
        "source_id": str(asset.get("source_id", "")),
        "source_document_id": str(asset.get("source_document_id", "")),
        "title": str(asset.get("title", "")),
        "raw_file": str(asset.get("raw_file", "")),
        "sidecar_file": str(asset.get("sidecar_file", "")),
        "media_type": str(asset.get("media_type", "")),
        "sha256": str(asset.get("sha256", "")),
        "map_signal_terms": _map_signal_terms(asset),
        "georeferencing_status": "not_georeferenced",
        "map_ocr_status": "not_extracted",
        "recommended_action": str(asset.get("recommended_action", "")),
        "suggested_next_actions": asset.get("suggested_next_actions", []),
        "review_status": str(asset.get("review_status", "")) or "unreviewed",
    }


def _map_signal_terms(asset: dict[str, Any]) -> list[str]:
    haystack = " ".join(
        str(asset.get(key, ""))
        for key in ("title", "raw_file", "sidecar_file", "source_document_id")
    ).casefold()
    return sorted(term for term in MAP_TERMS if term in haystack)


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un catalogo preview-only delle mappe storiche candidate.")
    parser.add_argument("--root-dir", default="data/raw")
    parser.add_argument("--input-plan-json", default="")
    parser.add_argument("--output-json", default="risultati/document_analysis/historical_map_catalog.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/historical_map_catalog.md")
    args = parser.parse_args()

    catalog = build_historical_map_catalog(
        root_dir=Path(args.root_dir),
        input_plan_json=Path(args.input_plan_json) if args.input_plan_json else None,
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"Catalogo mappe JSON scritto in {args.output_json}")
    print(f"Catalogo mappe Markdown scritto in {args.output_md}")
    print(f"Mappe candidate: {catalog['map_candidate_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
