from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.memoria_cli import main


class MemoriaCliPlaceEventPreviewTests(unittest.TestCase):
    def test_preview_commands_require_all_paths(self) -> None:
        for command in ("place-preview", "event-preview"):
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(["documents", command])
                self.assertEqual(error.exception.code, 2)

    def test_place_preview_dispatches_explicit_catalog_and_outputs_summary(self) -> None:
        report = {"place_id": "place:test", "counts": {"candidate_updates": 1}, "preview_only": True}
        args = ["documents", "place-preview", "--segments-dir", "segments", "--places-index-json", "index.json",
                "--place-jsonld", "place.jsonld", "--candidate-claims-json", "claims.json",
                "--source-documents-db", "catalog.sqlite", "--output-dir", "preview"]
        with patch("caduti_fonti_report.memoria_cli.run_place_preview", return_value=report) as run:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(args), 0)
        self.assertEqual(run.call_args.kwargs["source_documents_db"], Path("catalog.sqlite"))
        self.assertEqual(run.call_args.kwargs["output_dir"], Path("preview"))
        self.assertIn("place:test", stdout.getvalue())

    def test_event_preview_dispatches_and_errors_return_nonzero(self) -> None:
        report = {"event_id": "event:test", "counts": {"event_links": 1}, "preview_only": True}
        args = ["documents", "event-preview", "--segments-dir", "segments", "--events-index-json", "index.json",
                "--event-jsonld", "event.jsonld", "--candidate-claims-json", "claims.json",
                "--source-documents-db", "catalog.sqlite", "--output-dir", "preview"]
        with patch("caduti_fonti_report.memoria_cli.run_historical_event_preview", return_value=report) as run:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(args), 0)
        self.assertEqual(run.call_args.kwargs["source_documents_db"], Path("catalog.sqlite"))
        self.assertIn("event:test", stdout.getvalue())
        with patch("caduti_fonti_report.memoria_cli.run_historical_event_preview", side_effect=ValueError("blocked")):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)


if __name__ == "__main__":
    unittest.main()
