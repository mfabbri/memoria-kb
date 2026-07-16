from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.candidate_person_profiles import (  # noqa: E402
    build_candidate_person_profiles_from_documents,
    render_candidate_person_profiles_markdown,
)
from caduti_fonti_report.document_analysis.metadata_extraction import extract_document_metadata  # noqa: E402
from caduti_fonti_report.document_analysis.text_extraction import extract_document_text  # noqa: E402


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


class CandidatePersonProfilesFromDocumentsTests(unittest.TestCase):
    def test_builds_candidate_profiles_from_processed_csv_rows(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            raw_dir = tmp_dir / "raw"
            metadata_dir = tmp_dir / "metadata"
            processed_dir = tmp_dir / "processed"
            output_json = tmp_dir / "candidate_person_profiles.json"
            output_md = tmp_dir / "candidate_person_profiles.md"
            csv_path = raw_dir / "legacy_documents" / "caduti_purocielo.csv"
            csv_path.parent.mkdir(parents=True)
            csv_path.write_text(
                "nome,nascita,morte,ruolo_affiliazione,origine_sulla_lapide\n"
                "Andreoli Dino,17 maggio 1920,11 ottobre 1944,36a Brigata Garibaldi,Bologna\n"
                "Guazzaloca Laura,28 gennaio 1920,,infermiera,Faenza\n",
                encoding="utf-8-sig",
            )
            extract_document_metadata(root_dir=raw_dir, output_dir=metadata_dir)
            text_summary = extract_document_text(metadata_dir=metadata_dir, output_dir=processed_dir, raw_root_dir=raw_dir)
            text_paths = [Path(item["text_path"]) for item in text_summary["documents"]]

            payload = build_candidate_person_profiles_from_documents(
                text_dir=processed_dir,
                output_json=output_json,
                output_md=output_md,
                text_paths=text_paths,
            )
            markdown = render_candidate_person_profiles_markdown(payload)
            persisted = json.loads(output_json.read_text(encoding="utf-8"))
            output_md_exists = output_md.exists()

        candidates = payload["candidate_person_profiles"]
        self.assertEqual(payload["@type"], "CandidatePersonProfileSet")
        self.assertEqual(payload["candidate_profile_count"], 2)
        self.assertEqual(payload["tabular_document_count"], 1)
        self.assertEqual(candidates[0]["canonical_name"], "Andreoli Dino")
        self.assertEqual(candidates[0]["suggested_profile_id"], "person:purocielo:andreoli-dino")
        self.assertEqual(candidates[0]["birth"]["raw"], "17 maggio 1920")
        self.assertEqual(candidates[0]["death"]["raw"], "11 ottobre 1944")
        self.assertEqual(candidates[0]["formations"], ["36a Brigata Garibaldi"])
        self.assertEqual(candidates[0]["places"], ["Bologna"])
        self.assertEqual(candidates[0]["row_number"], 1)
        self.assertEqual(candidates[0]["promotion_status"], "not_promoted")
        self.assertEqual(candidates[0]["review_status"], "unreviewed")
        self.assertEqual(persisted["candidate_profile_count"], 2)
        self.assertTrue(output_md_exists)
        self.assertIn("Andreoli Dino", markdown)
        self.assertIn("person:purocielo:guazzaloca-laura", markdown)
        self.assertNotIn("PersonResearchProfile", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_skips_tabular_rows_without_person_name(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            processed_dir = tmp_dir / "processed"
            text_path = processed_dir / "legacy" / "table.text.json"
            text_path.parent.mkdir(parents=True)
            text_path.write_text(
                json.dumps(
                    {
                        "@type": "ProcessedDocumentText",
                        "source_id": "legacy_documents",
                        "source_document_id": "legacy:1",
                        "document_class": "tabular_document",
                        "text_status": "extracted",
                        "text": "Riga 1. nascita: 1920; ruolo: partigiano",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            payload = build_candidate_person_profiles_from_documents(text_dir=processed_dir)

        self.assertEqual(payload["candidate_profile_count"], 0)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["skipped_rows"][0]["reason"], "missing_person_name")

    def test_builds_targeted_candidate_profiles_from_unreviewed_mentions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            processed_dir = tmp_dir / "processed"
            text_path = processed_dir / "data_raw" / "doc.text.json"
            mentions_path = processed_dir / "data_raw" / "doc.mentions.json"
            text_path.parent.mkdir(parents=True)
            text_path.write_text(
                json.dumps(
                    {
                        "@type": "ProcessedDocumentText",
                        "source_id": "data_raw",
                        "source_document_id": "data_raw:doc",
                        "document_class": "word_document",
                        "text_status": "extracted",
                        "raw_file": "data_raw/manual_uploads/doc.docx",
                        "text": "Bianchi Osvaldo e Sante Vignuzzi",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            mentions_path.write_text(
                json.dumps(
                    {
                        "@type": "DocumentMentionCandidateDocument",
                        "source_id": "data_raw",
                        "source_document_id": "data_raw:doc",
                        "mention_count": 2,
                        "mentions": [
                            {
                                "@type": "PersonMentionCandidate",
                                "mention_id": "mention:bianchi",
                                "mention_kind": "person",
                                "value": "Bianchi Osvaldo",
                                "normalized_value": "bianchi osvaldo",
                                "source_id": "data_raw",
                                "source_document_id": "data_raw:doc",
                                "context": "Bianchi Osvaldo, Rico",
                                "weak_segment_id": "segment:1",
                                "chunk_id": "chunk:1",
                                "review_status": "unreviewed",
                            },
                            {
                                "@type": "PersonMentionCandidate",
                                "mention_id": "mention:vignuzzi",
                                "mention_kind": "person",
                                "value": "Sante Vignuzzi",
                                "normalized_value": "sante vignuzzi",
                                "source_id": "data_raw",
                                "source_document_id": "data_raw:doc",
                                "context": "Sante Vignuzzi",
                                "review_status": "unreviewed",
                            },
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            payload = build_candidate_person_profiles_from_documents(
                text_dir=processed_dir,
                text_paths=[text_path],
                target_names=["Bianchi Osvaldo"],
            )

        candidates = payload["candidate_person_profiles"]
        self.assertEqual(payload["candidate_profile_count"], 1)
        self.assertEqual(payload["target_names"], ["Bianchi Osvaldo"])
        self.assertEqual(candidates[0]["canonical_name"], "Bianchi Osvaldo")
        self.assertEqual(candidates[0]["suggested_profile_id"], "person:purocielo:bianchi-osvaldo")
        self.assertEqual(candidates[0]["source_document_id"], "data_raw:doc")
        self.assertEqual(candidates[0]["row_fields"]["mention_context"], "Bianchi Osvaldo, Rico")
        self.assertEqual(candidates[0]["provenance"]["extraction_method"], "processed_person_mention_target_match")
        self.assertEqual(candidates[0]["review_status"], "unreviewed")
        self.assertEqual(candidates[0]["promotion_status"], "not_promoted")


if __name__ == "__main__":
    unittest.main()
