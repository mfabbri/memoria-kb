#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=1; shift; fi
TARGET_ROOT="${1:-}"
if [[ -z "$TARGET_ROOT" ]]; then
  echo "Uso: ./apply.sh [--dry-run] /percorso/me.mo.ri.a-kb" >&2
  exit 2
fi

PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD_ROOT="$PACKAGE_ROOT/payload"
TARGET_ROOT="$(cd "$TARGET_ROOT" && pwd)"
[[ -d "$TARGET_ROOT/memoria-bootstrap" ]] || { echo "Destinazione non valida: manca memoria-bootstrap" >&2; exit 1; }

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="$TARGET_ROOT/.codex-migration-backup/discovery-fix-$STAMP"

while IFS= read -r -d '' src; do
  rel="${src#$PAYLOAD_ROOT/}"
  dst="$TARGET_ROOT/$rel"
  if [[ -f "$dst" ]]; then action=UPDATE; else action=CREATE; fi
  echo "$action $rel"
  [[ "$DRY_RUN" -eq 1 ]] && continue
  if [[ -f "$dst" ]]; then
    mkdir -p "$BACKUP_ROOT/$(dirname "$rel")"
    cp -p "$dst" "$BACKUP_ROOT/$rel"
  fi
  mkdir -p "$(dirname "$dst")"
  cp -p "$src" "$dst"
done < <(find "$PAYLOAD_ROOT" -type f -print0 | sort -z)

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run completato: nessun file modificato"
else
  [[ -d "$BACKUP_ROOT" ]] && echo "Backup: $BACKUP_ROOT"
  echo "Correzione discovery Codex applicata"
  echo "Riavvia Codex dalla radice del repository per ricaricare skill e configurazione"
fi
