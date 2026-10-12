from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from caduti_fonti_report.document_analysis.ocr_lexicon_candidates import build_document_lexicon_review
from caduti_fonti_report.memoria_cli import main


class DocumentOcrLexiconReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.structure = self.root / "structure.json"
        self.lexicon = self.root / "lexicon.json"
        self.glossary = self.root / "glossary.jsonld"
        self.output = self.root / "new" / "review.jsonld"
        self.structure_payload = {
            "@type": "DocumentStructure", "schema_version": "1.0", "page_id": "synthetic-page",
            "source_evidence": {"language": "deu", "source_image_hash": "synthetic-hash"},
            "blocks": [{"block_id": "b1", "text": "Es mur Decknamen sein 305.Inf.Div. Batl. XYZ. 000995",
                        "source_region_ids": ["r1", "r2"]}],
        }
        self.lexicon_payload = {
            "@type": "OcrLanguageLexicon", "schema_version": "1.0", "@id": "fixture:de",
            "language": "de", "version": "1", "entries": [
                {"term": term, "category": "word"} for term in ("Es", "nur", "Decknamen", "sein")],
        }
        self.glossary_payload = {
            "@type": "MilitaryGlossary", "@id": "fixture:military", "version": "2",
            "entries": [{"@id": "fixture:division", "term": "Infanteriedivision",
                         "abbreviations": ["Inf.Div."], "source_reference": "fixture:offline-reference"},
                        {"@id": "fixture:battalion", "term": "Bataillon", "abbreviations": ["Batl."]}],
        }
        self.write(self.structure, self.structure_payload)
        self.write(self.lexicon, self.lexicon_payload)
        self.write(self.glossary, self.glossary_payload)

    @staticmethod
    def write(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def review(self, **kwargs):
        return build_document_lexicon_review(structure_path=self.structure, lexicon_path=self.lexicon,
                                            output_path=self.output, **kwargs)

    def test_preview_diagnostics_and_provenance_preserve_all_tokens(self) -> None:
        original = self.structure.read_bytes()
        report = self.review(glossary_path=self.glossary)
        self.assertFalse(self.output.parent.exists())
        self.assertEqual(original, self.structure.read_bytes())
        self.assertEqual(report, self.review(glossary_path=self.glossary))
        block = report["blocks"][0]
        self.assertEqual(block["source_region_ids"], ["r1", "r2"])
        self.assertEqual(block["text"], self.structure_payload["blocks"][0]["text"])
        tokens = {t["raw_token"]: t for t in block["tokens"]}
        self.assertEqual(set(tokens), {"Es", "mur", "Decknamen", "sein", "305.", "Inf.Div.", "Batl.", "XYZ.", "000995"})
        self.assertEqual(tokens["Es"]["status"], "exact_match")
        self.assertEqual(tokens["mur"]["status"], "not_found")
        self.assertTrue(tokens["mur"]["needs_human_review"])
        self.assertEqual(tokens["mur"]["fuzzy_suggestions"][0]["term"], "nur")
        self.assertEqual(tokens["Inf.Div."]["token_kind"], "abbreviation")
        self.assertEqual(tokens["Inf.Div."]["exact_matches"][0]["source_id"], "fixture:division")
        self.assertEqual(tokens["XYZ."]["status"], "not_found")
        self.assertEqual(tokens["000995"]["status"], "non_word")
        for token in block["tokens"]:
            self.assertEqual(block["text"][token["start"]:token["end"]], token["raw_token"])
        self.assertEqual(report["source_structure_digest"], "sha256:" + hashlib.sha256(original).hexdigest())
        self.assertEqual(report["source_evidence"]["source_image_hash"], "synthetic-hash")
        self.assertEqual(report["resources"][1]["entry_provenance"][0]["source_reference"], "fixture:offline-reference")
        self.assertEqual(report["lexicon_completeness"], "not_asserted")
        self.assertEqual(report["abbreviation_check"], "run_with_explicit_glossary")
        self.assertTrue(report["preview_only"])
        self.assertFalse(report["claim_extraction_allowed"])

    def test_apply_is_idempotent_and_rejects_different_output(self) -> None:
        report = self.review(apply=True)
        self.assertEqual(report["operation_status"], "written")
        saved = self.output.read_bytes()
        self.assertEqual(self.review(apply=True)["operation_status"], "skipped_existing")
        self.assertEqual(saved, self.output.read_bytes())
        self.output.write_text("unrelated", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "diverso"):
            self.review(apply=True)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "unrelated")

    def test_no_glossary_and_unknown_word_remain_uncertain(self) -> None:
        report = self.review()
        tokens = {t["raw_token"]: t for t in report["blocks"][0]["tokens"]}
        self.assertEqual(tokens["Inf.Div."]["status"], "not_found")
        self.assertEqual(tokens["Inf.Div."]["token_kind"], "abbreviation")
        self.assertEqual(len(report["resources"]), 1)
        self.assertEqual(report["abbreviation_check"], "not_run")

    def test_declared_words_do_not_split_unknown_sigla_or_misclassify_uppercase_words(self) -> None:
        payload = self.lexicon_payload | {"entries": self.lexicon_payload["entries"] + [
            {"term": "Inf", "category": "word"}, {"term": "Div", "category": "word"}]}
        self.write(self.lexicon, payload)
        self.structure_payload["blocks"][0]["text"] = "DECKNAMEN Inf.Div. Es. Eo."
        self.write(self.structure, self.structure_payload)
        tokens = self.review()["blocks"][0]["tokens"]
        self.assertEqual([t["raw_token"] for t in tokens], ["DECKNAMEN", "Inf.Div.", "Es.", "Eo."])
        self.assertEqual(tokens[0]["token_kind"], "word")
        self.assertEqual(tokens[1]["status"], "not_found")
        self.assertEqual(tokens[2]["token_kind"], "word")
        self.assertEqual(tokens[2]["status"], "exact_match")
        self.assertEqual(tokens[3]["token_kind"], "word_or_abbreviation")
        self.assertEqual(tokens[3]["status"], "not_found")
        self.assertEqual(tokens[3]["fuzzy_suggestions"][0]["term"], "Es")

    def test_invalid_resources_and_missing_provenance_fail_closed(self) -> None:
        for mutation in (
            {"schema_version": "2"}, {"entries": "bad"}, {"version": ""},
            {"language": "en"}, {"entries": [{"term": "Es", "category": "unknown"}]},
        ):
            with self.subTest(mutation=mutation):
                self.write(self.lexicon, self.lexicon_payload | mutation)
                with self.assertRaises(ValueError):
                    self.review(apply=True)
                self.assertFalse(self.output.exists())
        self.write(self.lexicon, self.lexicon_payload)
        self.write(self.structure, self.structure_payload | {"blocks": [{"block_id": "b", "text": "Es"}]})
        with self.assertRaises(ValueError):
            self.review(apply=True)
        self.assertFalse(self.output.exists())

    def test_glossary_invalid_entries_fail_closed(self) -> None:
        for entries in (["bad"], [{"@id": "id", "term": "Term", "abbreviations": "ABC"}],
                        [{"term": "Term"}]):
            with self.subTest(entries=entries):
                self.write(self.glossary, self.glossary_payload | {"entries": entries})
                with self.assertRaises(ValueError):
                    self.review(glossary_path=self.glossary, apply=True)
                self.assertFalse(self.output.exists())

    def test_nested_pages_keep_page_identity_and_validate_schema(self) -> None:
        block = self.structure_payload["blocks"][0]
        payload = {k: v for k, v in self.structure_payload.items() if k != "blocks"}
        payload["pages"] = [{"page_id": "p2", "blocks": [block]}]
        self.write(self.structure, payload)
        self.assertEqual(self.review()["blocks"][0]["page_id"], "p2")
        self.write(self.structure, payload | {"schema_version": "2"})
        with self.assertRaises(ValueError):
            self.review()

    def test_cli_preview_apply_and_invalid_threshold(self) -> None:
        args = ["documents", "lexicon-review", "--structure", str(self.structure),
                "--lexicon", str(self.lexicon), "--output", str(self.output)]
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(stream.getvalue())["operation_status"], "preview")
        self.assertFalse(self.output.exists())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args + ["--apply"]), 0)
        self.assertTrue(self.output.exists())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args + ["--max-distance", "-1"]), 1)


if __name__ == "__main__":
    unittest.main()
