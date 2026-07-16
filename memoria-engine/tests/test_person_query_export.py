from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.adapters import matches_name_filter, person_queries_from_caduti
from caduti_fonti_report.config import load_caduti
from caduti_fonti_report.export_person_queries import build_person_queries_export, write_person_queries_export


@contextmanager
def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def write_caduti_fixture(path: Path) -> None:
    csv_text = (
        "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,fonti_richiamate,"
        "profilo_biografico,episodio_documentato\n"
        'ANDREOLI DINO,Andreoli Dino,Italia,"17 maggio 1920","11 ottobre 1944",partigiano,Fonte A,"Profilo A","Episodio A"\n'
        'PANOV SERGIO,Panov Sergio,U.R.S.S.,non reperito,non reperito,"partigiano sovietico",Fonte B,"Profilo B","Episodio B"\n'
        'GIORGIO,Giorgio,U.R.S.S.,non reperito,non reperito,"partigiano sovietico",,"",""\n'
    )
    path.write_text(csv_text, encoding="utf-8-sig")


class PersonQueryExportTests(unittest.TestCase):
    def test_person_queries_from_caduti_converts_all_rows(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            csv_path = tmp_dir / "caduti.csv"
            write_caduti_fixture(csv_path)
            caduti = load_caduti(csv_path)

        queries = person_queries_from_caduti(caduti)

        self.assertEqual(len(queries), 3)
        self.assertEqual(queries[0].full_name, "Andreoli Dino")
        self.assertEqual(queries[0].metadata["intestazione_pdf"], "ANDREOLI DINO")

    def test_matches_name_filter_checks_name_and_pdf_heading(self) -> None:
        self.assertTrue(matches_name_filter("panov", "Panov Sergio", "PANOV SERGIO"))
        self.assertTrue(matches_name_filter("sergio panov", "Panov Sergio", "SERGIO PANOV"))
        self.assertFalse(matches_name_filter("andreoli", "Panov Sergio", "PANOV SERGIO"))

    def test_build_export_applies_limit_and_serializes(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            csv_path = tmp_dir / "caduti.csv"
            write_caduti_fixture(csv_path)
            payload = build_person_queries_export(csv_path=csv_path, limit=2)

        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["person_queries"][0]["full_name"], "Andreoli Dino")
        json.dumps(payload)

    def test_build_export_applies_name_filter(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            csv_path = tmp_dir / "caduti.csv"
            write_caduti_fixture(csv_path)
            payload = build_person_queries_export(csv_path=csv_path, name_filter="Panov")

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["person_queries"][0]["full_name"], "Panov Sergio")

    def test_write_export_creates_output_json(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            csv_path = tmp_dir / "caduti.csv"
            output_path = tmp_dir / "out" / "person_queries.json"
            write_caduti_fixture(csv_path)
            payload = write_person_queries_export(csv_path=csv_path, output_json_path=output_path, limit=1)
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["count"], 1)
        self.assertEqual(written["count"], 1)
        self.assertEqual(written["person_queries"][0]["metadata"]["nome"], "Andreoli Dino")


if __name__ == "__main__":
    unittest.main()
