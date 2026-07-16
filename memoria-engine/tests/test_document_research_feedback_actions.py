from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.research_feedback_actions import (  # noqa: E402
    build_document_research_feedback_actions,
    render_research_feedback_actions_markdown,
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


def write_mentions_payload(
    root_dir: Path,
    *,
    source_id: str = "manual_uploads",
    source_document_id: str = "doc:signals",
    mentions: list[dict[str, object]],
) -> Path:
    mentions_dir = root_dir / source_id
    mentions_dir.mkdir(parents=True, exist_ok=True)
    path = mentions_dir / f"{source_document_id.replace(':', '-')}.mentions.json"
    payload = {
        "@type": "DocumentMentionCandidateDocument",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "segments_file": f"{source_id}/{source_document_id}.weak-segments.json",
        "review_status": "unreviewed",
        "mention_count": len(mentions),
        "mentions": mentions,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def mention(
    *,
    mention_kind: str,
    value: str,
    weak_segment_id: str = "weak-document-segment:1",
    chunk_id: str = "physical-document-chunk:1",
    confidence: float = 0.62,
) -> dict[str, object]:
    mention_id = f"document-mention-candidate:{mention_kind}:{value.replace(' ', '-').lower()}"
    return {
        "@type": f"{mention_kind.title().replace('_', '')}MentionCandidate",
        "@id": mention_id,
        "mention_id": mention_id,
        "mention_kind": mention_kind,
        "value": value,
        "normalized_value": value.casefold(),
        "source_id": "manual_uploads",
        "source_document_id": "doc:signals",
        "segments_file": "doc.weak-segments.json",
        "chunk_id": chunk_id,
        "chunk_index": 1,
        "weak_segment_id": weak_segment_id,
        "segment_type": "person_mention_context",
        "segment_char_start": 0,
        "segment_char_end": len(value),
        "context": f"Contesto con {value}",
        "confidence": confidence,
        "reasons": [f"{mention_kind}_pattern"],
        "warnings": ["mention_candidate_not_verified_fact"],
        "candidate_profile_id": "",
        "claim_extraction_allowed": False,
        "extraction_method": "deterministic_mention_candidate_rules",
        "review_status": "unreviewed",
    }


class DocumentResearchFeedbackActionsTests(unittest.TestCase):
    def test_builds_research_feedback_actions_from_supported_person_mentions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            mentions_dir = tmp_dir / "mentions"
            output_dir = tmp_dir / "actions"
            output_json = tmp_dir / "research_feedback_actions.json"
            output_md = tmp_dir / "research_feedback_actions.md"
            write_mentions_payload(
                mentions_dir,
                mentions=[
                    mention(mention_kind="person", value="Andreoli Dino"),
                    mention(mention_kind="formation", value="36a Brigata Garibaldi", confidence=0.7),
                    mention(mention_kind="archival_reference", value="RH 36/117/3", confidence=0.78),
                ],
            )

            payload = build_document_research_feedback_actions(
                mentions_dir=mentions_dir,
                output_dir=output_dir,
                output_json=output_json,
                output_md=output_md,
            )
            document = payload["documents"][0]
            action = document["actions"][0]
            persisted = json.loads(
                (output_dir / "manual_uploads" / "doc-signals.research-feedback-actions.json").read_text("utf-8")
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        self.assertEqual(payload["@type"], "ResearchFeedbackActionSet")
        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["action_count"], 1)
        self.assertEqual(document["@type"], "ResearchFeedbackActionDocument")
        self.assertEqual(document["review_status"], "unreviewed")
        self.assertEqual(persisted["action_count"], 1)
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertEqual(action["@type"], "ResearchFeedbackAction")
        self.assertEqual(action["trigger_type"], "weak_candidate")
        self.assertEqual(action["action_kind"], "request_source_specific_search")
        self.assertEqual(action["value"], "Andreoli Dino")
        self.assertEqual(action["review_status"], "unreviewed")
        self.assertEqual(action["risk"], "high")
        self.assertIn("storia_memoria_bo", action["suggested_sources"])
        self.assertIn("partigiani_italia", action["suggested_sources"])
        self.assertIn("bundesarchiv_invenio", action["suggested_sources"])
        hint_fields = {hint["field"] for hint in action["suggested_search_hints"]}
        self.assertEqual(hint_fields, {"person_name", "formation", "archival_reference"})
        self.assertIn("research_feedback_action_not_verified_fact", action["warnings"])
        self.assertIn("support_scope:same_segment", action["warnings"])
        self.assertEqual(action["context"]["support_scope"], "same_segment")
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("ProfilePatch", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_person_mentions_without_supporting_context_stay_mentions_only(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            mentions_dir = tmp_dir / "mentions"
            write_mentions_payload(
                mentions_dir,
                mentions=[mention(mention_kind="person", value="Andreoli Dino")],
            )

            payload = build_document_research_feedback_actions(mentions_dir=mentions_dir)

        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["action_count"], 0)
        self.assertEqual(payload["documents"][0]["actions"], [])
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_place_and_date_mentions_support_research_feedback_actions(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            mentions_dir = tmp_dir / "mentions"
            write_mentions_payload(
                mentions_dir,
                mentions=[
                    mention(mention_kind="person", value="Andreoli Dino"),
                    mention(mention_kind="place", value="Purocielo", confidence=0.66),
                    mention(mention_kind="date", value="11 ottobre 1944", confidence=0.74),
                ],
            )

            payload = build_document_research_feedback_actions(mentions_dir=mentions_dir)

        action = payload["documents"][0]["actions"][0]
        hint_fields = {hint["field"] for hint in action["suggested_search_hints"]}
        self.assertEqual(payload["action_count"], 1)
        self.assertEqual(action["risk"], "medium")
        self.assertEqual(hint_fields, {"person_name", "place", "date"})
        self.assertIn("person_mention_with_place", action["reasons"])
        self.assertIn("person_mention_with_date", action["reasons"])
        self.assertNotIn("bundesarchiv_invenio", action["suggested_sources"])
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("ProfilePatch", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_supporting_mentions_can_share_chunk_when_segments_are_separate(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            mentions_dir = tmp_dir / "mentions"
            write_mentions_payload(
                mentions_dir,
                mentions=[
                    mention(mention_kind="person", value="Andreoli Dino", weak_segment_id="weak-document-segment:1"),
                    mention(
                        mention_kind="formation",
                        value="36a Brigata Garibaldi",
                        weak_segment_id="weak-document-segment:2",
                    ),
                ],
            )

            payload = build_document_research_feedback_actions(mentions_dir=mentions_dir)

        action = payload["documents"][0]["actions"][0]
        self.assertEqual(payload["action_count"], 1)
        self.assertEqual(action["context"]["support_scope"], "same_chunk")
        self.assertIn("support_scope:same_chunk", action["warnings"])
        self.assertIn("36a Brigata Garibaldi", json.dumps(action["suggested_search_hints"]))

    def test_place_or_date_support_can_share_chunk_when_segments_are_separate(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            mentions_dir = tmp_dir / "mentions"
            write_mentions_payload(
                mentions_dir,
                mentions=[
                    mention(mention_kind="person", value="Andreoli Dino", weak_segment_id="weak-document-segment:1"),
                    mention(mention_kind="place", value="Ca' di Malanca", weak_segment_id="weak-document-segment:2"),
                    mention(mention_kind="date", value="ottobre 1944", weak_segment_id="weak-document-segment:3"),
                ],
            )

            payload = build_document_research_feedback_actions(mentions_dir=mentions_dir)

        action = payload["documents"][0]["actions"][0]
        self.assertEqual(payload["action_count"], 1)
        self.assertEqual(action["context"]["support_scope"], "same_chunk")
        self.assertIn("support_scope:same_chunk", action["warnings"])
        self.assertIn("Ca' di Malanca", json.dumps(action["suggested_search_hints"]))
        self.assertIn("ottobre 1944", json.dumps(action["suggested_search_hints"]))

    def test_supporting_mentions_must_share_chunk(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            mentions_dir = tmp_dir / "mentions"
            write_mentions_payload(
                mentions_dir,
                mentions=[
                    mention(
                        mention_kind="person",
                        value="Andreoli Dino",
                        weak_segment_id="weak-document-segment:1",
                        chunk_id="physical-document-chunk:1",
                    ),
                    mention(
                        mention_kind="formation",
                        value="36a Brigata Garibaldi",
                        weak_segment_id="weak-document-segment:2",
                        chunk_id="physical-document-chunk:2",
                    ),
                ],
            )

            payload = build_document_research_feedback_actions(mentions_dir=mentions_dir)

        self.assertEqual(payload["action_count"], 0)

    def test_skips_invalid_mention_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            mentions_dir = tmp_dir / "mentions"
            mentions_dir.mkdir()
            (mentions_dir / "bad.mentions.json").write_text(
                json.dumps({"@type": "WeakDocumentSegmentDocument", "source_document_id": "doc:bad"}),
                encoding="utf-8",
            )

            payload = build_document_research_feedback_actions(mentions_dir=mentions_dir)

        self.assertEqual(payload["document_count"], 0)
        self.assertEqual(payload["action_count"], 0)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "unsupported_payload_type")

    def test_markdown_renderer_lists_actions_for_review(self) -> None:
        payload = {
            "generation_method": "deterministic_research_feedback_action_rules",
            "document_count": 1,
            "action_count": 1,
            "skipped_count": 0,
            "documents": [
                {
                    "source_document_id": "doc:1",
                    "source_id": "manual_uploads",
                    "review_status": "unreviewed",
                    "action_count": 1,
                    "mentions_file": "doc.mentions.json",
                    "actions": [
                        {
                            "action_id": "research-feedback-action:abc",
                            "value": "Andreoli Dino",
                            "priority": "medium",
                            "risk": "medium",
                            "suggested_sources": ["storia_memoria_bo"],
                        }
                    ],
                }
            ],
        }

        markdown = render_research_feedback_actions_markdown(payload)

        self.assertIn("# ResearchFeedbackAction preview", markdown)
        self.assertIn("research-feedback-action:abc", markdown)
        self.assertIn("Andreoli Dino", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
