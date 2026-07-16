from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_DIRS = ("profili_pilota", "fonti_online", "scansioni", "docx_testuali", "html_salvati")
TEXT_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".docx"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


def build_mvp_document_intake_preflight(
    *,
    workspace_root: Path,
    pilot_profiles_json: Path | None = None,
    output_json: Path | None = None,
    output_md: Path | None = None,
    ensure_structure: bool = False,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    pilot_profiles_json = pilot_profiles_json or workspace_root / "ricerche" / "mvp" / "pilot_profiles.purocielo.json"
    mvp_documents_root = workspace_root / "documenti_da_processare" / "mvp_purocielo"

    directories = _required_directories(mvp_documents_root, ensure_structure=ensure_structure)
    profiles, profile_warnings = _load_pilot_profiles(pilot_profiles_json)
    documents, sidecar_count = _scan_documents(mvp_documents_root)
    blockers = _blockers(
        pilot_profiles_json=pilot_profiles_json,
        pilot_profile_count=len(profiles),
        mvp_documents_root=mvp_documents_root,
        required_directories=directories,
        documents=documents,
        sidecar_count=sidecar_count,
    )

    payload = {
        "@type": "MvpDocumentIntakePreflight",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": "unreviewed",
        "publication_status": "not_publishable_without_human_review",
        "workspace_root": str(workspace_root),
        "pilot_profiles_json": str(pilot_profiles_json),
        "pilot_profile_count": len(profiles),
        "mvp_documents_root": str(mvp_documents_root),
        "ensure_structure": ensure_structure,
        "required_directories": directories,
        "document_count": len(documents),
        "sidecar_count": sidecar_count,
        "text_like_document_count": sum(1 for item in documents if item["document_kind"] == "text_like"),
        "image_document_count": sum(1 for item in documents if item["document_kind"] == "image"),
        "other_document_count": sum(1 for item in documents if item["document_kind"] == "other"),
        "documents": documents,
        "blockers": blockers,
        "warnings": profile_warnings,
        "next_action": _next_action(blockers),
        "note": "Preview-only: non modifica raw, profili, sidecar o claim.",
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_mvp_document_intake_preflight_markdown(payload), encoding="utf-8")
    return payload


def render_mvp_document_intake_preflight_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "---",
        "type: mvp_document_intake_preflight",
        f"review_status: {payload.get('review_status', 'unreviewed')}",
        f"publication_status: {payload.get('publication_status', 'not_publishable_without_human_review')}",
        "---",
        "",
        "# Preflight documenti pilota MVP",
        "",
        "Report preview-only: verifica struttura e segnali minimi senza validare fatti storici.",
        "",
        "## Workspace",
        "",
        f"- Root operativa: `{payload.get('workspace_root', '')}`",
        f"- Profili pilota: `{payload.get('pilot_profiles_json', '')}`",
        f"- Root documenti MVP: `{payload.get('mvp_documents_root', '')}`",
        "",
        "## Sintesi",
        "",
        f"- Profili pilota letti: `{payload.get('pilot_profile_count', 0)}`",
        f"- Documenti rilevati: `{payload.get('document_count', 0)}`",
        f"- Sidecar rilevati: `{payload.get('sidecar_count', 0)}`",
        f"- Testuali: `{payload.get('text_like_document_count', 0)}`",
        f"- Immagini: `{payload.get('image_document_count', 0)}`",
        f"- Altri formati: `{payload.get('other_document_count', 0)}`",
        "",
        "## Cartelle richieste",
        "",
        "| Cartella | Stato | Creata ora |",
        "|---|---:|---:|",
    ]
    for item in _list_items(payload.get("required_directories")):
        status = "presente" if item.get("exists") else "mancante"
        created = "si" if item.get("created") else "no"
        lines.append(f"| `{item.get('path', '')}` | {status} | {created} |")

    lines.extend(["", "## Blocker", ""])
    blockers = _list_strings(payload.get("blockers"))
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("_Nessun blocker strutturale rilevato._")

    lines.extend(["", "## Documenti rilevati", ""])
    documents = _list_items(payload.get("documents"))
    if documents:
        lines.extend(["| Documento | Tipo | Sidecar |", "|---|---:|---:|"])
        for item in documents[:100]:
            sidecar = "si" if item.get("sidecar_exists") else "no"
            lines.append(f"| `{item.get('relative_path', '')}` | {item.get('document_kind', '')} | {sidecar} |")
        if len(documents) > 100:
            lines.append(f"| ... | altri {len(documents) - 100} documenti | ... |")
    else:
        lines.append("_Nessun documento rilevato nella root MVP._")

    lines.extend(
        [
            "",
            "## Prossima azione",
            "",
            str(payload.get("next_action", "")),
            "",
            "## Vincoli",
            "",
            "- La cartella `docs` resta solo nel repository Git.",
            "- Tutti gli artefatti operativi restano sotto `P:\\Comune\\Me.Mo.Ri.a`.",
            "- Nessun raw, profilo, sidecar o claim viene modificato da questo report.",
            "",
        ]
    )
    return "\n".join(lines)


def _required_directories(root: Path, *, ensure_structure: bool) -> list[dict[str, Any]]:
    paths = [root, *(root / name for name in REQUIRED_DIRS)]
    items: list[dict[str, Any]] = []
    for path in paths:
        existed = path.is_dir()
        created = False
        if ensure_structure and not existed:
            path.mkdir(parents=True, exist_ok=True)
            created = True
        items.append(
            {
                "name": path.name,
                "path": str(path),
                "exists": path.is_dir(),
                "created": created,
            }
        )
    return items


def _load_pilot_profiles(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"File profili pilota non trovato: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return [], [f"File profili pilota non leggibile come JSON: {path} ({exc})"]
    if isinstance(data, list):
        profiles = data
    elif isinstance(data, dict):
        profiles = data.get("profiles") or data.get("items") or data.get("@graph") or []
    else:
        profiles = []
    return [item for item in profiles if isinstance(item, dict)], []


def _scan_documents(root: Path) -> tuple[list[dict[str, Any]], int]:
    if not root.is_dir():
        return [], 0
    documents: list[dict[str, Any]] = []
    sidecar_count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _is_sidecar(path):
            sidecar_count += 1
            continue
        extension = path.suffix.lower()
        documents.append(
            {
                "relative_path": str(path.relative_to(root)),
                "path": str(path),
                "extension": extension,
                "document_kind": _document_kind(extension),
                "sidecar_exists": _sidecar_exists(path),
            }
        )
    return documents, sidecar_count


def _blockers(
    *,
    pilot_profiles_json: Path,
    pilot_profile_count: int,
    mvp_documents_root: Path,
    required_directories: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    sidecar_count: int,
) -> list[str]:
    blockers: list[str] = []
    if not pilot_profiles_json.exists():
        blockers.append(f"Manca la selezione profili pilota: {pilot_profiles_json}")
    elif pilot_profile_count == 0:
        blockers.append(f"La selezione profili pilota non contiene profili leggibili: {pilot_profiles_json}")
    if not mvp_documents_root.is_dir():
        blockers.append(f"Manca la root documenti MVP: {mvp_documents_root}")
    missing_dirs = [item["path"] for item in required_directories if not item.get("exists")]
    if missing_dirs:
        blockers.append("Mancano cartelle intake MVP: " + ", ".join(missing_dirs))
    if not documents:
        blockers.append("Nessun documento rilevato in documenti_da_processare\\mvp_purocielo.")
    missing_sidecars = [item for item in documents if not item.get("sidecar_exists")]
    if missing_sidecars:
        blockers.append(f"{len(missing_sidecars)} documenti non hanno sidecar per-file o document.yaml di cartella.")
    if documents and sidecar_count < len(documents):
        blockers.append("Il numero di sidecar e' inferiore al numero di documenti rilevati.")
    return blockers


def _next_action(blockers: list[str]) -> str:
    joined = "\n".join(blockers)
    if "root documenti MVP" in joined or "cartelle intake MVP" in joined:
        return "Creare la struttura con -EnsureStructure, poi raccogliere i documenti pilota sotto documenti_da_processare\\mvp_purocielo."
    if "Nessun documento" in joined:
        return "Copiare 15-30 documenti reali pilota nel workspace operativo e aggiungere i sidecar minimi."
    if "sidecar" in joined:
        return "Completare i sidecar e la provenance prima di eseguire il wrapper MVP."
    return "Eseguire run_mvp_workspace_pipeline.ps1 con -InputRootDir puntato a P:\\Comune\\Me.Mo.Ri.a\\documenti_da_processare\\mvp_purocielo."


def _document_kind(extension: str) -> str:
    if extension in TEXT_EXTENSIONS:
        return "text_like"
    if extension in IMAGE_EXTENSIONS:
        return "image"
    return "other"


def _is_sidecar(path: Path) -> bool:
    name = path.name.lower()
    return name == "document.yaml" or name.endswith(".document.yaml") or name.endswith(".document.yml")


def _sidecar_exists(path: Path) -> bool:
    return (
        path.with_name(path.name + ".document.yaml").exists()
        or path.with_name(path.name + ".document.yml").exists()
        or (path.parent / "document.yaml").exists()
        or (path.parent / "document.yml").exists()
    )


def _list_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight document intake MVP.")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--pilot-profiles-json")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    parser.add_argument("--ensure-structure", action="store_true")
    args = parser.parse_args(argv)

    build_mvp_document_intake_preflight(
        workspace_root=Path(args.workspace_root),
        pilot_profiles_json=Path(args.pilot_profiles_json) if args.pilot_profiles_json else None,
        output_json=Path(args.output_json) if args.output_json else None,
        output_md=Path(args.output_md) if args.output_md else None,
        ensure_structure=args.ensure_structure,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
