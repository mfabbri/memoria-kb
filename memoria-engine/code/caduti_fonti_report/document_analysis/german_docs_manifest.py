from __future__ import annotations

from typing import Any


def render_german_docs_manifest_markdown(manifest: dict[str, Any]) -> str:
    node_label = manifest.get("node_url") or manifest.get("opis_url", "")
    title_label = manifest.get("node_title") or manifest.get("opis_title", "")
    lines = [
        "# German Docs in Russia download manifest",
        "",
        f"Source: `{manifest.get('source_id', '')}`",
        f"Node: {node_label}",
        f"Title: {title_label}",
        f"Archival reference: {manifest.get('archival_reference', '')}",
        f"Output dir: `{manifest.get('output_dir', '')}`",
        f"Detected pages: {manifest.get('page_count_detected', 0)}",
        "",
    ]
    context_payload = manifest.get("archival_context", {})
    hierarchy = context_payload.get("hierarchy", []) if isinstance(context_payload, dict) else []
    if hierarchy:
        lines.extend(["## Archival Context", ""])
        for item in hierarchy:
            metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
            lines.append(f"- `{item.get('level', '')}` {item.get('title', '')}")
            lines.append(f"  URL: {item.get('url', '')}")
            if isinstance(metadata, dict):
                for key, value in list(metadata.items())[:4]:
                    excerpt = str(value)
                    if len(excerpt) > 240:
                        excerpt = excerpt[:237].rstrip() + "..."
                    lines.append(f"  - {key}: {excerpt}")
            lines.append("")
    delo_nodes = manifest.get("delo_nodes", [])
    if isinstance(delo_nodes, list) and delo_nodes:
        lines.extend(["## Delo Nodes", ""])
        for delo in delo_nodes:
            if not isinstance(delo, dict):
                continue
            lines.append(
                f"- {delo.get('title', '')} - detected pages: {delo.get('page_count_detected', 0)} "
                f"- output: `{delo.get('output_dir', '')}`"
            )
        lines.append("")
    lines.extend(["## Documents", ""])
    for item in manifest.get("documents", []):
        lines.append(
            f"- `{item.get('status', '')}` page {item.get('page_number', '')} "
            f"page_id `{item.get('page_id', '')}` -> `{item.get('file', '')}`"
        )
    return "\n".join(lines).rstrip() + "\n"
