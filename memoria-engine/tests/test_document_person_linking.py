from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.person_linking import (  # noqa: E402
    _load_json_object,
    build_candidate_document_person_links,
    render_candidate_document_person_links_markdown,
)


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


def write_profile_index(root_dir: Path) -> Path:
    profiles_dir = root_dir / "profiles"
    profiles_dir.mkdir()
    profiles = [
        {
            "@id": "person:purocielo:guazzaloca-laura",
            "file": "purocielo-guazzaloca-laura.jsonld",
            "canonical_name": "Guazzaloca Laura",
            "identity": {
                "canonical_name": "Guazzaloca Laura",
                "given_name": "Laura",
                "family_name": "Guazzaloca",
                "aliases": [],
                "name_forms": ["Guazzaloca Laura", "Laura", "Guazzaloca"],
            },
        },
        {
            "@id": "person:purocielo:memo-moretti-renato",
            "file": "purocielo-memo-moretti-renato.jsonld",
            "canonical_name": "Moretti Renato",
            "identity": {
                "canonical_name": "Moretti Renato",
                "given_name": "Renato",
                "family_name": "Moretti",
                "aliases": ["Memo Moretti"],
                "name_forms": ["Moretti Renato", "Renato", "Moretti", "Memo Moretti"],
            },
        },
        {
            "@id": "person:purocielo:il-toscano",
            "file": "purocielo-il-toscano.jsonld",
            "canonical_name": "Il Toscano",
            "identity": {
                "canonical_name": "Il Toscano",
                "given_name": "",
                "family_name": "",
                "aliases": [],
                "name_forms": ["Il Toscano"],
            },
            "search_hints": [
                {
                    "hint_id": "hint:identity-alias:toscano-ignoto",
                    "source_id": "seed",
                    "field": "identity.alias",
                    "value": "Toscano Ignoto",
                    "confidence": 0.5,
                    "provenance": "seed.alias",
                    "review_status": "unreviewed",
                }
            ],
        },
        {
            "@id": "person:purocielo:giorgio",
            "file": "purocielo-giorgio.jsonld",
            "canonical_name": "Giorgio",
            "identity": {
                "canonical_name": "Giorgio",
                "given_name": "Giorgio",
                "family_name": "",
                "aliases": [],
                "name_forms": ["Giorgio"],
            },
        },
    ]
    for profile in profiles:
        payload = {
            "@type": "PersonResearchProfile",
            "@id": profile["@id"],
            "profile_id": profile["@id"],
            "identity": profile["identity"],
            "seed": {"source": "test", "source_id": "", "imported_at": "", "payload": {}},
            "birth": {},
            "death": {},
            "formations": [],
            "events": [],
            "places": [],
            "search_hints": profile.get("search_hints", []),
            "evidence_claim_ids": [],
            "verified_facts": {},
            "conflicts": [],
            "searched_sources": [],
            "next_research": [],
            "metadata": {},
        }
        (profiles_dir / profile["file"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    index = {
        "@type": "ca:PersonResearchProfileIndex",
        "profiles": [
            {"@id": profile["@id"], "file": profile["file"], "canonical_name": profile["canonical_name"]}
            for profile in profiles
        ],
    }
    index_path = profiles_dir / "purocielo.index.jsonld"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def write_processed_document(
    root_dir: Path,
    *,
    source_id: str = "camalanca_html",
    source_document_id: str = "doc-1",
    document_class: str = "html_document",
    text_status: str = "extracted",
    claim_eligible: bool = True,
    text: str,
) -> tuple[Path, Path]:
    metadata_dir = root_dir / "metadata"
    text_dir = root_dir / "text"
    (metadata_dir / source_id).mkdir(parents=True)
    (text_dir / source_id).mkdir(parents=True)
    metadata_path = metadata_dir / source_id / f"{source_document_id}.metadata.json"
    text_path = text_dir / source_id / f"{source_document_id}.text.json"
    metadata = {
        "@type": "ProcessedDocumentMetadata",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "title": "Scheda locale",
        "document_class": document_class,
        "claim_eligible": claim_eligible,
        "review_status": "unreviewed",
        "raw_file": "raw/document.html",
        "media_type": "text/html",
        "url": "https://www.camalanca.it/scheda/",
        "archival_reference": "",
    }
    text_payload = {
        "@type": "ProcessedDocumentText",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "document_class": document_class,
        "claim_eligible": claim_eligible,
        "review_status": "unreviewed",
        "metadata_file": str(metadata_path),
        "text_status": text_status,
        "extraction_status": "text_extracted" if text_status == "extracted" else "skipped",
        "text": text,
        "text_length": len(text),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    text_path.write_text(json.dumps(text_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_dir, text_dir


class DocumentPersonLinkingTests(unittest.TestCase):
    def test_builds_reviewable_links_without_claims_or_profile_writes(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text="La scheda cita Guazzaloca Laura e Memo Moretti come persone collegate.",
            )
            output_json = tmp_dir / "candidate_document_person_links.json"
            output_md = tmp_dir / "candidate_document_person_links.md"

            payload = build_candidate_document_person_links(
                text_dir=text_dir,
                metadata_dir=metadata_dir,
                profiles_index=profiles_index,
                output_json=output_json,
                output_md=output_md,
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

            links = payload["candidate_document_person_links"]
            by_name = {link["matched_name"]: link for link in links}
            self.assertEqual(payload["@type"], "CandidateDocumentPersonLinkSet")
            self.assertEqual(payload["link_count"], 2)
            self.assertEqual(by_name["Guazzaloca Laura"]["profile_id"], "person:purocielo:guazzaloca-laura")
            self.assertEqual(by_name["Memo Moretti"]["profile_id"], "person:purocielo:memo-moretti-renato")
            self.assertEqual(by_name["Guazzaloca Laura"]["review_status"], "unreviewed")
            self.assertIn("exact_canonical_name_match", by_name["Guazzaloca Laura"]["reasons"])
            self.assertIn("Guazzaloca Laura", by_name["Guazzaloca Laura"]["context"])
            self.assertEqual(by_name["Guazzaloca Laura"]["score"], 1.0)
            self.assertTrue(output_json_exists)
            self.assertTrue(output_md_exists)
            self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
            self.assertNotIn("verified_facts", json.dumps(payload))

    def test_builds_segment_scoped_links_from_document_mentions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text="Documento multi-scheda con Guazzaloca Laura e Memo Moretti.",
            )
            mentions_path = text_dir / "camalanca_html" / "doc-1.mentions.json"
            mentions_path.write_text(
                json.dumps(
                    {
                        "@type": "DocumentMentionCandidateDocument",
                        "source_id": "camalanca_html",
                        "source_document_id": "doc-1",
                        "mentions": [
                            {
                                "@type": "PersonMentionCandidate",
                                "@id": "document-mention-candidate:guazzaloca",
                                "mention_kind": "person",
                                "value": "Guazzaloca Laura",
                                "normalized_value": "guazzaloca laura",
                                "source_id": "camalanca_html",
                                "source_document_id": "doc-1",
                                "chunk_id": "physical-document-chunk:doc-1:1",
                                "weak_segment_id": "weak-document-segment:doc-1:guazzaloca",
                                "context": "Guazzaloca Laura, nata il 28 gennaio 1920.",
                                "confidence": 0.71,
                                "reasons": ["capitalized_person_name_pattern"],
                                "review_status": "unreviewed",
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            payload = build_candidate_document_person_links(text_dir=text_dir, metadata_dir=metadata_dir, profiles_index=profiles_index)

        guazzaloca = [link for link in payload["candidate_document_person_links"] if link["profile_id"] == "person:purocielo:guazzaloca-laura"][0]
        self.assertEqual(guazzaloca["weak_segment_id"], "weak-document-segment:doc-1:guazzaloca")
        self.assertEqual(guazzaloca["chunk_id"], "physical-document-chunk:doc-1:1")
        self.assertIn("segment_name_match", guazzaloca["reasons"])
        self.assertIn("Guazzaloca Laura, nata", guazzaloca["context"])

    def test_matches_controlled_punctuation_variants_without_fuzzy_matching(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text="La trascrizione cita Guazzaloca-Laura e Memo/Moretti nella stessa pagina.",
            )

            payload = build_candidate_document_person_links(
                text_dir=text_dir,
                metadata_dir=metadata_dir,
                profiles_index=profiles_index,
            )

        links = payload["candidate_document_person_links"]
        by_name = {link["matched_name"]: link for link in links}
        self.assertEqual(payload["link_count"], 2)
        self.assertIn("normalized_canonical_name_match", by_name["Guazzaloca Laura"]["reasons"])
        self.assertIn("normalized_alias_match", by_name["Memo Moretti"]["reasons"])
        self.assertEqual(by_name["Guazzaloca Laura"]["score"], 0.92)
        self.assertEqual(by_name["Memo Moretti"]["review_status"], "unreviewed")
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))

    def test_uses_identity_search_hints_as_unreviewed_link_candidates_only(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                text="Nel documento appare Toscano Ignoto come possibile persona collegata.",
            )

            payload = build_candidate_document_person_links(
                text_dir=text_dir,
                metadata_dir=metadata_dir,
                profiles_index=profiles_index,
            )

        links = payload["candidate_document_person_links"]
        self.assertEqual(payload["link_count"], 1)
        self.assertEqual(links[0]["profile_id"], "person:purocielo:il-toscano")
        self.assertEqual(links[0]["match_kind"], "search_hint_alias")
        self.assertEqual(links[0]["score"], 0.85)
        self.assertEqual(links[0]["review_status"], "unreviewed")
        self.assertIn("exact_search_hint_alias_match", links[0]["reasons"])
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_ignores_single_token_profile_names_to_reduce_false_positives(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            metadata_dir, text_dir = write_processed_document(tmp_dir, text="Nel testo compare Giorgio senza altri dati.")

            payload = build_candidate_document_person_links(
                text_dir=text_dir,
                metadata_dir=metadata_dir,
                profiles_index=profiles_index,
            )

        self.assertEqual(payload["link_count"], 0)

    def test_skips_result_pages_even_when_text_mentions_a_profile(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            metadata_dir, text_dir = write_processed_document(
                tmp_dir,
                document_class="result_page",
                claim_eligible=False,
                text="Risultati ricerca per Guazzaloca Laura.",
            )

            payload = build_candidate_document_person_links(
                text_dir=text_dir,
                metadata_dir=metadata_dir,
                profiles_index=profiles_index,
            )

        self.assertEqual(payload["link_count"], 0)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "skipped_result_page")

    def test_unreadable_path_is_skipped_without_crashing(self) -> None:
        path = Path("data/processed/documents/unreadable.text.json")

        with patch.object(Path, "exists", return_value=True), patch.object(Path, "is_file", side_effect=OSError("stat failed")):
            payload = _load_json_object(path)

        self.assertEqual(payload, {})

    def test_deduplicates_same_profile_on_same_document_hash_across_sources(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            profiles_index = write_profile_index(tmp_dir)
            metadata_dir = tmp_dir / "metadata"
            text_dir = tmp_dir / "text"
            for source_id, document_id, raw_file in [
                ("html_copy", "html-copy:299da50ff847a4f3", "alfonso-bagni.html"),
                ("manual_uploads", "manual_uploads:299da50ff847a4f3", "manual_uploads/alfonso-bagni.html"),
            ]:
                (metadata_dir / source_id).mkdir(parents=True)
                (text_dir / source_id).mkdir(parents=True)
                metadata_path = metadata_dir / source_id / f"{document_id.replace(':', '-')}.metadata.json"
                text_path = text_dir / source_id / f"{document_id.replace(':', '-')}.text.json"
                metadata = {
                    "@type": "ProcessedDocumentMetadata",
                    "source_id": source_id,
                    "source_document_id": document_id,
                    "title": "guazzaloca-laura.html",
                    "document_class": "html_document",
                    "claim_eligible": True,
                    "review_status": "unreviewed",
                    "raw_file": raw_file,
                    "media_type": "text/html",
                }
                text_payload = {
                    "@type": "ProcessedDocumentText",
                    "source_id": source_id,
                    "source_document_id": document_id,
                    "document_class": "html_document",
                    "claim_eligible": True,
                    "review_status": "unreviewed",
                    "metadata_file": str(metadata_path),
                    "text_status": "extracted",
                    "extraction_status": "text_extracted",
                    "text": "La scheda cita Guazzaloca Laura.",
                    "text_length": 29,
                }
                metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
                text_path.write_text(json.dumps(text_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            payload = build_candidate_document_person_links(
                text_dir=text_dir,
                metadata_dir=metadata_dir,
                profiles_index=profiles_index,
            )

        self.assertEqual(payload["link_count"], 1)
        self.assertEqual(payload["candidate_document_person_links"][0]["profile_id"], "person:purocielo:guazzaloca-laura")

    def test_markdown_renderer_lists_links_for_review(self) -> None:
        payload = {
            "profiles_index": "profiles/index.jsonld",
            "link_count": 1,
            "skipped_count": 0,
            "candidate_document_person_links": [
                {
                    "matched_name": "Guazzaloca Laura",
                    "profile_id": "person:purocielo:guazzaloca-laura",
                    "source_document_id": "doc-1",
                    "source_id": "camalanca_html",
                    "title": "Scheda locale",
                    "review_status": "unreviewed",
                    "score": 1.0,
                    "reasons": ["exact_canonical_name_match"],
                    "context": "Testo con Guazzaloca Laura.",
                }
            ],
        }

        markdown = render_candidate_document_person_links_markdown(payload)

        self.assertIn("# CandidateDocumentPersonLink preview", markdown)
        self.assertIn("person:purocielo:guazzaloca-laura", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
