#!/usr/bin/env python3
"""Read-only, bounded view of Me.Mo.Ri.A planner. Does not alter current-work.json."""
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=Path(__file__).with_name('current-work.json'))
    args = parser.parse_args()
    with args.file.open(encoding='utf-8') as stream:
        doc = json.load(stream)
    increment = doc.get('increment') or {}
    next_action = doc.get('next_action') or {}
    routing = doc.get('routing') or {}
    # Do not dump the large session_notes list or accidentally echo secrets.
    for key, value in (
        ('status', doc.get('status')),
        ('increment', increment.get('id')),
        ('title', increment.get('title')),
        ('updated_at', doc.get('updated_at')),
        ('verification', (doc.get('verification') or {}).get('result')),
        ('next_action', next_action.get('mode')),
        ('next_description', next_action.get('description')),
        ('routing_policy', routing.get('policy_version')),
        ('history_notes', len(doc.get('session_notes') or [])),
    ):
        print(f'{key}: {str(value)[:360]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
