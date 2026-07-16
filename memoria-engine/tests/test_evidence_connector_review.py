from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.evidence_connector_review import run_evidence_connector_review


def workspace_temp_dir():
    base_dir = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base_dir.mkdir(exist_ok=True)
    tmp_dir = base_dir / f"test-{uuid.uuid4().hex}"
    tmp_dir.mkdir()
    return tmp_dir


class EvidenceConnectorReviewTests(unittest.TestCase):
    def test_review_runs_selected_legacy_source_and_writes_outputs(self) -> None:
        tmp_dir = workspace_temp_dir()
        try:
            csv_path = tmp_dir / "caduti.csv"
            yaml_path = tmp_dir / "fonti.yaml"
            output_md = tmp_dir / "review.md"
            output_json = tmp_dir / "review.json"
            csv_path.write_text(
                (
                    "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,"
                    "fonti_richiamate,profilo_biografico,episodio_documentato\n"
                    'ROSSI MARIO,Rossi Mario,Italia,1900,1944,partigiano,Fonte,"Profilo","Episodio"\n'
                ),
                encoding="utf-8-sig",
            )
            yaml_path.write_text(
                """
enabled_sources:
  - source_a
sources:
  - id: source_a
    name: Source A
    kind: search_url_only
    query_mode: default
    url_template: https://example.test/search?q={query}
""",
                encoding="utf-8",
            )

            result = run_evidence_connector_review(
                csv_path=csv_path,
                sources_yaml=yaml_path,
                output_md=output_md,
                output_json=output_json,
                source_ids=["source_a"],
                limit=1,
                run_id="test-review",
            )

            output_md_exists = output_md.exists()
            payload = json.loads(output_json.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(output_md_exists)
        self.assertEqual(payload["run_id"], "test-review")
        self.assertEqual(payload["sources"][0]["registration"]["connector_type"], "LegacyConnectorAdapter")
        self.assertEqual(payload["sources"][0]["caduti"][0]["results"][0]["result"]["status"], "search_url_ready")

    def test_review_runs_partigiani_italia_with_uniform_connector(self) -> None:
        tmp_dir = workspace_temp_dir()
        try:
            csv_path = tmp_dir / "caduti.csv"
            yaml_path = tmp_dir / "fonti.yaml"
            output_md = tmp_dir / "review.md"
            output_json = tmp_dir / "review.json"
            csv_path.write_text(
                (
                    "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,"
                    "fonti_richiamate,profilo_biografico,episodio_documentato\n"
                    'ANDREOLI DINO,Andreoli Dino,Italia,"17 maggio 1920","1944",partigiano,Fonte,"Profilo","Episodio"\n'
                ),
                encoding="utf-8-sig",
            )
            yaml_path.write_text(
                """
enabled_sources:
  - partigiani_italia
sources:
  - id: partigiani_italia
    name: I Partigiani d'Italia - ricerca pubblica
    kind: search_form_get_name
    query_mode: default
    url_template: https://partigianiditalia.cultura.gov.it/cerca/
    form:
      name_order: "surname_first"
""",
                encoding="utf-8",
            )

            with patch(
                "caduti_fonti_report.connectors.http_get_form_executor.fetch_text",
                side_effect=lambda url, timeout: (
                    "<html><body><h1>Risultati</h1><a href=\"/persona/?id=123\">ANDREOLI DINO</a></body></html>"
                    if "/cerca/" in url
                    else "<html><body><p>La consultazione dei dati è consentita esclusivamente agli utenti registrati. Esegui il login.</p></body></html>"
                ),
            ):
                result = run_evidence_connector_review(
                    csv_path=csv_path,
                    sources_yaml=yaml_path,
                    output_md=output_md,
                    output_json=output_json,
                    source_ids=["partigiani_italia"],
                    limit=1,
                    run_id="test-review",
                    repo_root=Path(__file__).resolve().parents[1],
                )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(payload["sources"][0]["registration"]["connector_type"], "UniformSourceConnector")
        self.assertEqual(payload["sources"][0]["registration"]["detail_fetch"], "detail_page")

    def test_review_closes_connector_even_when_fetch_detail_raises(self) -> None:
        tmp_dir = workspace_temp_dir()
        try:
            csv_path = tmp_dir / "caduti.csv"
            yaml_path = tmp_dir / "fonti.yaml"
            output_md = tmp_dir / "review.md"
            output_json = tmp_dir / "review.json"
            csv_path.write_text(
                (
                    "intestazione_pdf,nome,origine_sulla_lapide,nascita,morte,ruolo_affiliazione,"
                    "fonti_richiamate,profilo_biografico,episodio_documentato\n"
                    'ROSSI MARIO,Rossi Mario,Italia,1900,1944,partigiano,Fonte,"Profilo","Episodio"\n'
                ),
                encoding="utf-8-sig",
            )
            yaml_path.write_text(
                """
enabled_sources:
  - source_a
sources:
  - id: source_a
    name: Source A
    kind: search_url_only
    query_mode: default
    url_template: https://example.test/search?q={query}
""",
                encoding="utf-8",
            )

            close_calls: list[str] = []

            class FailingConnector:
                def search_person(self, query):
                    return [SimpleNamespace(status="ok", query=query.full_name, hits=[], search_url="https://example.test/result")]

                def fetch_detail(self, result):
                    raise RuntimeError("detail failed")

                def extract_evidence(self, document):
                    return []

                def close(self):
                    close_calls.append("closed")

            with patch(
                "caduti_fonti_report.evidence_connector_review.create_source_connector",
                return_value=FailingConnector(),
            ), patch(
                "caduti_fonti_report.evidence_connector_review.describe_source_connector",
                return_value=SimpleNamespace(
                    connector_type="FailingConnector",
                    evidence_aware=True,
                    detail_fetch="detail_page",
                    claim_extraction="detail_logic",
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "detail failed"):
                    run_evidence_connector_review(
                        csv_path=csv_path,
                        sources_yaml=yaml_path,
                        output_md=output_md,
                        output_json=output_json,
                        source_ids=["source_a"],
                        limit=1,
                        run_id="test-close-on-error",
                    )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        self.assertEqual(close_calls, ["closed"])


if __name__ == "__main__":
    unittest.main()
