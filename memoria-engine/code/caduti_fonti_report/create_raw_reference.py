from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import to_json_safe
from .raw_store import RawDocumentStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea un documento raw reference-only.")
    parser.add_argument("--root-dir", default="data/raw")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--query", default="")
    args = parser.parse_args()

    store = RawDocumentStore(Path(args.root_dir))
    document = store.save_reference_document(
        source_id=args.source_id,
        title=args.title,
        url=args.url,
        reason=args.reason,
        query=args.query,
    )
    print(json.dumps(to_json_safe(document), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
