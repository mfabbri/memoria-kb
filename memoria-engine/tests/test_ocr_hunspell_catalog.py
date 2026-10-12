from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from caduti_fonti_report.document_analysis.ocr_hunspell_catalog import (
    build_hunspell_lexicon, export_hunspell_lexicon,
)
from caduti_fonti_report.document_analysis.ocr_lexicon_candidates import build_document_lexicon_review
from caduti_fonti_report.memoria_cli import main


class SyntheticLookup:
    """Test double for a single synthetic suffix; not a Hunspell implementation."""

    def __init__(self, dic: Path, aff: Path):
        suffix = aff.read_text(encoding="utf-8").splitlines()[-1].split()[3]
        self.forms = set()
        for entry in dic.read_text(encoding="utf-8").splitlines()[1:]:
            stem, _, flag = entry.partition("/")
            self.forms.add(stem)
            if flag == "S":
                self.forms.add(stem + suffix)

    def lookup(self, word: str) -> bool:
        return word in self.forms


class OcrHunspellCatalogTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = self.root / "catalog.json"
        self.output = self.root / "new" / "lexicon.json"
        self.resources = []
        self.examples = {"ita": ("libro", "libroide"), "ita_old": ("arca", "arcaide"),
                         "eng": ("book", "books"), "rus": ("книга", "книгами"),
                         "deu": ("Deckname", "Decknamen")}
        for language, (stem, form) in self.examples.items():
            # The invented Italian/Russian forms deliberately assert no linguistic validity.
            (self.root / (language + ".dic")).write_text("1\n" + stem + "/S\n", encoding="utf-8")
            suffix = form[len(stem):]
            (self.root / (language + ".aff")).write_text(
                "SET UTF-8\nSFX S Y 1\nSFX S 0 " + suffix + " .\n", encoding="utf-8")
            self.resources.append({"@id": "fixture:" + language, "language": language,
                                   "variant": "synthetic", "upstream": "fixture:offline:" + language,
                                   "revision": "synthetic-1", "license": "synthetic-test-only",
                                   "dic": language + ".dic", "aff": language + ".aff"})
        self.save_catalog()

    def save_catalog(self):
        self.catalog.write_text(json.dumps({"@type": "OcrHunspellCatalog", "schema_version": "1.0",
                                            "resources": self.resources}), encoding="utf-8")

    def build(self, language="deu", **kwargs):
        return build_hunspell_lexicon(catalog_path=self.catalog, language=language,
                                     terms=[*self.examples[language], "not-a-known-word"],
                                     backend_factory=SyntheticLookup, backend_id="synthetic-test-double",
                                     backend_version="1", **kwargs)

    def test_all_languages_and_sampled_inflections_have_specific_provenance(self):
        for language in self.examples:
            with self.subTest(language=language):
                payload = self.build(language)
                self.assertEqual({entry["term"] for entry in payload["entries"]}, set(self.examples[language]))
                self.assertEqual(payload["not_found_terms"], ["not-a-known-word"])
                provenance = payload["provenance"]
                self.assertEqual(provenance["upstream"], "fixture:offline:" + language)
                self.assertEqual(provenance["backend"]["id"], "synthetic-test-double")
                self.assertEqual(provenance["metadata_status"], "owner_declared_not_independently_verified")
                for kind in ("dic", "aff"):
                    expected = "sha256:" + hashlib.sha256((self.root / (language + "." + kind)).read_bytes()).hexdigest()
                    self.assertEqual(provenance["inputs"][kind]["digest"], expected)
                self.assertTrue(all(entry["provenance"] == provenance for entry in payload["entries"]))
                self.assertEqual(payload["lexicon_completeness"], "not_asserted")
                self.assertEqual(payload, self.build(language))

    def test_variants_require_explicit_resolution(self):
        alternate = self.resources[-1] | {"@id": "fixture:de-alt", "variant": "alternate", "revision": "2"}
        self.resources.append(alternate)
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "ambigua"):
            self.build()
        self.assertEqual(self.build(variant="alternate")["version"], "2")
        with self.assertRaises(ValueError):
            self.build(variant="missing")

    def test_missing_metadata_duplicate_and_digest_mismatch_fail_closed(self):
        original = dict(self.resources[-1])
        for field in ("@id", "language", "variant", "upstream", "revision", "license", "dic", "aff"):
            with self.subTest(field=field):
                self.resources[-1] = original | {field: ""}
                self.save_catalog()
                with self.assertRaises(ValueError):
                    self.build()
        self.resources[-1] = original | {"dic_digest": "sha256:" + "0" * 64}
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "Digest"):
            self.build()
        self.resources[-1] = original
        self.resources.append(original)
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "duplicata"):
            self.build()

    def test_missing_pair_incompatible_pair_and_changed_inputs_fail_closed(self):
        self.resources[-1]["aff"] = "eng.aff"
        self.save_catalog()
        with self.assertRaisesRegex(ValueError, "Coppia"):
            self.build()
        self.resources[-1]["aff"] = "missing.aff"
        self.resources[-1]["dic"] = "missing.dic"
        self.save_catalog()
        with self.assertRaises(OSError):
            self.build()
        self.resources[-1].update(aff="deu.aff", dic="deu.dic")
        self.save_catalog()

        def mutate(dic, aff):
            backend = SyntheticLookup(dic, aff)
            aff.write_text("changed", encoding="utf-8")
            return backend

        with self.assertRaisesRegex(ValueError, "modificata"):
            build_hunspell_lexicon(catalog_path=self.catalog, language="deu", terms=["Deckname"],
                                  backend_factory=mutate, backend_id="synthetic-mutator", backend_version="1")

    def test_preview_export_and_existing_reviewer_preserve_raw_structure(self):
        kwargs = dict(catalog_path=self.catalog, language="deu", terms=["Deckname", "Decknamen", "noise"],
                      backend_factory=SyntheticLookup, backend_id="synthetic-test-double", backend_version="1",
                      output_path=self.output)
        self.assertEqual(export_hunspell_lexicon(**kwargs)["operation_status"], "preview")
        self.assertFalse(self.output.parent.exists())
        self.assertEqual(export_hunspell_lexicon(**kwargs, apply=True)["operation_status"], "written")
        self.assertEqual(export_hunspell_lexicon(**kwargs, apply=True)["operation_status"], "skipped_existing")
        structure = self.root / "structure.json"
        structure.write_text(json.dumps({"@type": "DocumentStructure", "schema_version": "1.0",
                                         "page_id": "fixture:p", "language": "deu",
                                         "blocks": [{"block_id": "b", "text": "Decknamen noise",
                                                     "source_region_ids": ["fixture:r"]}]}), encoding="utf-8")
        before = structure.read_bytes()
        report = build_document_lexicon_review(structure_path=structure, lexicon_path=self.output,
                                               output_path=self.root / "review.json")
        self.assertEqual(before, structure.read_bytes())
        self.assertTrue(report["raw_ocr_unchanged"])
        self.assertEqual([t["status"] for t in report["blocks"][0]["tokens"]], ["exact_match", "not_found"])
        self.output.write_text("unrelated", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "diverso"):
            export_hunspell_lexicon(**kwargs, apply=True)

    def test_backend_missing_and_incompatible_fail_with_explicit_errors(self):
        with patch.dict("sys.modules", {"spylls": None, "spylls.hunspell": None}):
            with self.assertRaisesRegex(ValueError, "Backend Hunspell assente"):
                build_hunspell_lexicon(catalog_path=self.catalog, language="deu", terms=["Deckname"])
        with self.assertRaisesRegex(ValueError, "backend_id"):
            build_hunspell_lexicon(catalog_path=self.catalog, language="deu", terms=["Deckname"],
                                  backend_factory=SyntheticLookup)
        with self.assertRaisesRegex(ValueError, "Nessun termine"):
            build_hunspell_lexicon(catalog_path=self.catalog, language="deu", terms=["noise"],
                                  backend_factory=SyntheticLookup, backend_id="synthetic", backend_version="1")

    def test_cli_export_preview_and_apply_with_explicit_backend_double(self):
        terms = self.root / "terms.json"
        terms.write_text('["Decknamen"]', encoding="utf-8")
        args = ["documents", "hunspell-lexicon", "--catalog", str(self.catalog), "--language", "deu",
                "--terms", str(terms), "--output", str(self.output)]

        def export(**kwargs):
            return export_hunspell_lexicon(**kwargs, backend_factory=SyntheticLookup,
                                          backend_id="synthetic-test-double", backend_version="1")

        with patch("caduti_fonti_report.memoria_cli.export_hunspell_lexicon", side_effect=export):
            stream = io.StringIO()
            with redirect_stdout(stream):
                self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(stream.getvalue())["operation_status"], "preview")
            self.assertFalse(self.output.exists())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args + ["--apply"]), 0)
            terms.write_text('{}', encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)

    @unittest.skipUnless(importlib.util.find_spec("spylls"), "optional spylls backend not installed")
    def test_real_optional_backend_checks_synthetic_affix(self):
        payload = build_hunspell_lexicon(catalog_path=self.catalog, language="deu", terms=["Decknamen", "noise"])
        self.assertEqual([entry["term"] for entry in payload["entries"]], ["Decknamen"])
        self.assertEqual(payload["provenance"]["backend"]["id"], "spylls.hunspell")


if __name__ == "__main__":
    unittest.main()
