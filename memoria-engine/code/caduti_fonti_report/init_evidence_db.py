from __future__ import annotations

import argparse
from pathlib import Path

from .sqlite_store import SQLiteEvidenceStore


def init_evidence_db(db_path: Path) -> None:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()


def main() -> int:
    parser = argparse.ArgumentParser(description="Inizializza il database SQLite delle evidenze.")
    parser.add_argument("--db", default="data/evidence.sqlite", help="Percorso del database SQLite.")
    args = parser.parse_args()

    db_path = Path(args.db)
    init_evidence_db(db_path)
    print(f"Database evidenze inizializzato: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
