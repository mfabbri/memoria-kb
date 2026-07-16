from __future__ import annotations

import argparse
from pathlib import Path

from .authenticated_session import ManualAuthenticatedPlaywrightSession, source_uses_manual_authenticated_session
from .config import load_source_registry


def ensure_authenticated_session(*, source_id: str, sources_yaml: Path, repo_root: Path | None = None) -> dict[str, str]:
    repo_root = repo_root or Path.cwd()
    source_registry = load_source_registry(sources_yaml)
    if source_id not in source_registry:
        available = ", ".join(sorted(source_registry))
        raise ValueError(f"Fonte non trovata nel registry: {source_id}. Fonti disponibili: {available}")

    source = source_registry[source_id]
    if not source_uses_manual_authenticated_session(source):
        raise ValueError(f"La fonte {source_id} non e' configurata per manual_persistent_context.")

    with ManualAuthenticatedPlaywrightSession(source, repo_root=repo_root) as session:
        state = session.ensure_authenticated()
        return {
            "source_id": source.source_id,
            "state": state.state,
            "checked_url": state.checked_url,
            "note": state.note,
            "profile_dir": session.policy.profile_dir,
            "audit_log_path": session.policy.audit_log_path,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apre o riusa una sessione autenticata Playwright persistente.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--sources-yaml", default="ricerche/camalanca_fonti.yaml")
    args = parser.parse_args()

    result = ensure_authenticated_session(
        source_id=args.source,
        sources_yaml=Path(args.sources_yaml),
    )
    print(f"Fonte: {result['source_id']}")
    print(f"Stato: {result['state']}")
    print(f"URL controllo: {result['checked_url']}")
    print(f"Note: {result['note']}")
    print(f"Profilo: {result['profile_dir']}")
    print(f"Audit: {result['audit_log_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
