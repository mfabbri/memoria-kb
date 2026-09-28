from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.glossary_revision import build_glossary_preview  # noqa: E402
from caduti_fonti_report.memoria_cli import main as memoria_main  # noqa: E402


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


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class GlossaryRevisionTests(unittest.TestCase):
    def test_preview_is_read_only_and_records_version_digest(self) -> None:
        with workspace_temp_dir() as tmp:
            structure, glossary, output = _fixtures(tmp)
            result = build_glossary_preview(
                structure_path=structure, glossary_path=glossary, output_path=output, apply=False
            )

            self.assertEqual(result["operation_status"], "preview")
            self.assertFalse(output.exists())
            self.assertEqual(result["glossary_version"], "2026-09-28.1")
            self.assertTrue(result["glossary_digest"].startswith("sha256:"))
            self.assertEqual(result["mention_count"], 1)
            self.assertEqual(result["mentions"][0]["matched_text"], "Gen.Kdo.")
            self.assertFalse(result["mentions"][0]["claim_extraction_allowed"])

    def test_apply_is_idempotent_and_cli_defaults_to_preview(self) -> None:
        with workspace_temp_dir() as tmp:
            structure, glossary, output = _fixtures(tmp)
            stdout = StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(
                    memoria_main(
                        [
                            "documents", "glossary-preview",
                            "--structure", str(structure), "--glossary", str(glossary), "--output", str(output),
                        ]
                    ),
                    0,
                )
            self.assertFalse(output.exists())
            self.assertIn("preview read-only", stdout.getvalue())

            first = build_glossary_preview(
                structure_path=structure, glossary_path=glossary, output_path=output, apply=True
            )
            second = build_glossary_preview(
                structure_path=structure, glossary_path=glossary, output_path=output, apply=True
            )
            self.assertEqual(first["operation_status"], "written")
            self.assertEqual(second["operation_status"], "skipped_existing")
            persisted = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(persisted["glossary_version"], "2026-09-28.1")


def _fixtures(tmp: Path) -> tuple[Path, Path, Path]:
    structure = tmp / "structure.json"
    glossary = tmp / "glossary.jsonld"
    output = tmp / "preview.jsonld"
    write_json(
        structure,
        {
            "@type": "DocumentStructure",
            "source_document_id": "T314-1275-00150",
            "page_id": "page-1",
            "pages": [{"blocks": [{"id": "r1", "text": "Gen.Kdo. an der Futa-Passstraße", "source_region_ids": ["ocr-r1"]}]}],
        },
    )
    write_json(
        glossary,
        {
            "@id": "military-glossary:de:test",
            "@type": "MilitaryGlossary",
            "version": "2026-09-28.1",
            "entries": [{
                "@id": "military-glossary-entry:de:gen-kdo",
                "term": "Generalkommando",
                "language": "de",
                "category": "command",
                "abbreviations": ["Gen.Kdo."],
                "translation_it": "comando generale",
                "source_reference": "https://example.test/source",
            }],
        },
    )
    return structure, glossary, output


if __name__ == "__main__":
    unittest.main()
