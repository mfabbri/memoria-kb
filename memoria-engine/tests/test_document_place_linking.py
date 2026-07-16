from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.place_linking import (  # noqa: E402
    build_candidate_document_place_links,
    render_candidate_document_place_links_markdown,
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


def write_places_index(root_dir: Path, *, ambiguous: bool = False) -> Path:
    places_dir = root_dir / "places"
    places_dir.mkdir()
    places = [
        {
            "@type": "PlaceResearchIdentity",
            "@id": "place:camalanca:purocielo",
            "place_id": "place:camalanca:purocielo",
            "preferred_label": "Purocielo",
            "alternate_labels": ["Puro Cielo"],
            "review_status": "unreviewed",
            "provenance": "test_fixture",
        },
        {
            "@type": "PlaceResearchIdentity",
            "@id": "place:camalanca:ca-di-malanca",
            "place_id": "place:camalanca:ca-di-malanca",
            "preferred_label": "Ca' di Malanca",
            "alternate_labels": ["Ca di Malanca"],
            "review_status": "unreviewed",
            "provenance": "test_fixture",
        },
    ]
    if ambiguous:
        places.append(
            {
                "@type": "PlaceResearchIdentity",
                "@id": "place:camalanca:purocielo-altro",
                "place_id": "place:camalanca:purocielo-altro",
                "preferred_label": "Altro Purocielo",
                "alternate_labels": ["Purocielo"],
                "review_status": "unreviewed",
                "provenance": "test_fixture",
            }
        )
    entries = []
    for place in places:
        filename = f"{place['place_id'].rsplit(':', 1)[-1]}.jsonld"
        (places_dir / filename).write_text(json.dumps(place, ensure_ascii=False, indent=2), encoding="utf-8")
        entries.append({"@id": place["place_id"], "file": filename, "preferred_label": place["preferred_label"]})
    index_path = places_dir / "places.index.jsonld"
    index_path.write_text(
        json.dumps(
            {"@type": "PlaceResearchIdentityIndex", "review_status": "unreviewed", "places": entries},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return index_path


def write_mentions(root_dir: Path, value: str = "Purocielo", *, context: str | None = None) -> Path:
    mentions_dir = root_dir / "mentions"
    source_dir = mentions_dir / "manual"
    source_dir.mkdir(parents=True)
    payload = {
        "@type": "DocumentMentionCandidateDocument",
        "source_id": "manual",
        "source_document_id": "doc-1",
        "review_status": "unreviewed",
        "mentions": [
            {
                "@type": "PlaceMentionCandidate",
                "@id": "document-mention-candidate:place",
                "mention_id": "document-mention-candidate:place",
                "mention_kind": "place",
                "value": value,
                "normalized_value": value.casefold(),
                "source_id": "manual",
                "source_document_id": "doc-1",
                "chunk_id": "physical-document-chunk:doc-1:1",
                "weak_segment_id": "weak-document-segment:doc-1:1",
                "context": context or f"Andreoli Dino a {value}",
                "confidence": 0.66,
                "candidate_place_id": "",
                "review_status": "unreviewed",
            }
        ],
    }
    (source_dir / "doc-1.mentions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return mentions_dir


def write_mentions_payload(root_dir: Path, mentions: list[dict[str, object]]) -> Path:
    mentions_dir = root_dir / "mentions"
    source_dir = mentions_dir / "manual"
    source_dir.mkdir(parents=True)
    payload = {
        "@type": "DocumentMentionCandidateDocument",
        "source_id": "manual",
        "source_document_id": "doc-1",
        "review_status": "unreviewed",
        "mentions": mentions,
    }
    (source_dir / "doc-1.mentions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return mentions_dir


def place_mention(mention_id: str, value: str, *, weak_segment_id: str, context: str) -> dict[str, object]:
    return {
        "@type": "PlaceMentionCandidate",
        "@id": mention_id,
        "mention_id": mention_id,
        "mention_kind": "place",
        "value": value,
        "normalized_value": value.casefold(),
        "source_id": "manual",
        "source_document_id": "doc-1",
        "chunk_id": "physical-document-chunk:doc-1:1",
        "weak_segment_id": weak_segment_id,
        "context": context,
        "confidence": 0.66,
        "candidate_place_id": "",
        "review_status": "unreviewed",
    }


class DocumentPlaceLinkingTests(unittest.TestCase):
    def test_builds_reviewable_place_links_from_unique_catalog_match(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            places_index = write_places_index(tmp_dir)
            mentions_dir = write_mentions(tmp_dir, value="Purocielo")
            output_json = tmp_dir / "candidate_document_place_links.json"
            output_md = tmp_dir / "candidate_document_place_links.md"

            payload = build_candidate_document_place_links(
                mentions_dir=mentions_dir,
                places_index=places_index,
                output_json=output_json,
                output_md=output_md,
            )
            self.assertTrue(output_json.exists())
            self.assertTrue(output_md.exists())

        self.assertEqual(payload["@type"], "CandidateDocumentPlaceLinkSet")
        self.assertEqual(payload["link_count"], 1)
        self.assertEqual(payload["skipped_mention_count"], 0)
        link = payload["candidate_document_place_links"][0]
        self.assertEqual(link["@type"], "CandidateDocumentPlaceLink")
        self.assertEqual(link["place_id"], "place:camalanca:purocielo")
        self.assertEqual(link["mention_id"], "document-mention-candidate:place")
        self.assertEqual(link["review_status"], "unreviewed")
        self.assertIn("place_link_not_verified_fact", link["warnings"])
        self.assertIn("place_link_not_person_presence", link["warnings"])
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_alias_match_is_preview_only(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            payload = build_candidate_document_place_links(
                mentions_dir=write_mentions(tmp_dir, value="Puro Cielo"),
                places_index=write_places_index(tmp_dir),
            )

        link = payload["candidate_document_place_links"][0]
        self.assertEqual(link["place_id"], "place:camalanca:purocielo")
        self.assertEqual(link["match_kind"], "alternate_label")
        self.assertEqual(link["score"], 0.9)

    def test_unknown_place_mentions_are_skipped_for_review(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            payload = build_candidate_document_place_links(
                mentions_dir=write_mentions(tmp_dir, value="Luogo Sconosciuto"),
                places_index=write_places_index(tmp_dir),
            )

        self.assertEqual(payload["link_count"], 0)
        self.assertEqual(payload["skipped_mention_count"], 1)
        self.assertEqual(payload["skipped_mentions"][0]["reason"], "place_not_found")

    def test_ambiguous_place_labels_do_not_link(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            payload = build_candidate_document_place_links(
                mentions_dir=write_mentions(tmp_dir, value="Purocielo"),
                places_index=write_places_index(tmp_dir, ambiguous=True),
            )

        self.assertEqual(payload["link_count"], 0)
        self.assertEqual(payload["skipped_mention_count"], 1)
        self.assertEqual(payload["skipped_mentions"][0]["reason"], "ambiguous_place_label")

    def test_navigation_context_is_skipped_without_removing_mentions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            payload = build_candidate_document_place_links(
                mentions_dir=write_mentions(
                    tmp_dir,
                    value="Ca' di Malanca",
                    context="Ca' di Malanca Salta al contenuto Ca' di Malanca Centro di Documentazione Menu Home",
                ),
                places_index=write_places_index(tmp_dir),
            )

        self.assertEqual(payload["link_count"], 0)
        self.assertEqual(payload["skipped_mention_count"], 1)
        self.assertEqual(payload["skipped_mentions"][0]["reason"], "navigation_or_boilerplate_context")
        self.assertEqual(payload["skipped_mentions"][0]["value"], "Ca' di Malanca")

    def test_duplicate_place_links_in_same_segment_are_skipped_for_audit(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            payload = build_candidate_document_place_links(
                mentions_dir=write_mentions_payload(
                    tmp_dir,
                    [
                        place_mention(
                            "document-mention-candidate:place-1",
                            "Purocielo",
                            weak_segment_id="weak-document-segment:1",
                            context="L'11 ottobre durante la Battaglia di Purocielo.",
                        ),
                        place_mention(
                            "document-mention-candidate:place-2",
                            "Purocielo",
                            weak_segment_id="weak-document-segment:1",
                            context="La Battaglia di Purocielo coinvolse il territorio.",
                        ),
                    ],
                ),
                places_index=write_places_index(tmp_dir),
            )

        self.assertEqual(payload["link_count"], 1)
        self.assertEqual(payload["skipped_mention_count"], 1)
        self.assertEqual(payload["skipped_mentions"][0]["reason"], "duplicate_place_link_in_segment")

    def test_markdown_renderer_lists_place_links(self) -> None:
        markdown = render_candidate_document_place_links_markdown(
            {
                "@type": "CandidateDocumentPlaceLinkSet",
                "places_index": "../memoria-knowledge/places/places.index.jsonld",
                "link_count": 1,
                "skipped_mention_count": 0,
                "skipped_document_count": 0,
                "candidate_document_place_links": [
                    {
                        "matched_label": "Purocielo",
                        "place_id": "place:camalanca:purocielo",
                        "source_document_id": "doc-1",
                        "source_id": "manual",
                        "mention_id": "mention:1",
                        "review_status": "unreviewed",
                        "score": 1.0,
                        "reasons": ["normalized_preferred_label_match"],
                        "context": "Andreoli Dino a Purocielo",
                    }
                ],
            }
        )

        self.assertIn("CandidateDocumentPlaceLink preview", markdown)
        self.assertIn("place:camalanca:purocielo", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
