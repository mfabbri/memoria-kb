from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.entity_preview_review import (
    build_entity_preview_review_receipt,
    build_entity_preview_review_receipt_from_decisions,
    build_entity_preview_review_template,
    run_entity_preview_review_wizard,
)
from caduti_fonti_report.memoria_cli import main


class EntityPreviewReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1] / ".tmp-tests" / ("entity-preview-review-" + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.links = self.write("links.json", {"@type": "CandidateDocumentPlaceLinkSet",
            "candidate_document_place_links": [{"@id": "candidate-link:1", "source_document_id": "doc:1",
                "place_label": "Purocielo", "matched_label": "Purocielo", "context": "at Purocielo"}]})
        self.updates = self.write("updates.json", {"@type": "CandidatePlaceUpdateSet",
            "candidate_updates": [{"@id": "candidate-update:1", "source_document_ids": ["doc:1"],
                "field": "place.label", "candidate_value": "Purocielo", "source_claims": [
                    {"value": "Purocielo", "evidence_span": "a Purocielo", "source_url": "https://example.org",
                     "source_document_id": "doc:1"}]}]})
        self.manifest = self.write("manifest.json", {"@type": "PlacePreviewManifest", "preview_only": True,
            "requires_human_review": True, "artifacts": {"place_links": self.ref(self.links),
            "place_updates": self.ref(self.updates)}})

    def write(self, name: str, value: object) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def ref(path: Path) -> dict[str, str]:
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_template_covers_links_and_updates_without_prefilling_decisions(self) -> None:
        template = build_entity_preview_review_template(manifest_json=self.manifest)
        self.assertEqual([(item["artifact_kind"], item["candidate_id"]) for item in template["decisions"]],
                         [("candidate_link", "candidate-link:1"), ("candidate_update", "candidate-update:1")])
        self.assertTrue(all(item["decision"] == item["reviewer"] == item["reviewed_at"] == ""
                            for item in template["decisions"]))
        self.assertFalse(template["apply_allowed"])

    def test_receipt_requires_complete_provenance_bound_human_decisions(self) -> None:
        template = build_entity_preview_review_template(manifest_json=self.manifest)
        self.assertEqual(template["preview_manifest"]["sha256"], hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        for item in template["decisions"]:
            item.update({"decision": "accept_candidate", "reviewer": "reviewer:test",
                         "reviewed_at": "2026-11-07T20:00:00+01:00", "note": "fixture review"})
        decisions_path = self.write("decisions.json", template)
        originals = {path: path.read_bytes() for path in (self.manifest, self.links, self.updates, decisions_path)}
        receipt = build_entity_preview_review_receipt(manifest_json=self.manifest, decisions_json=decisions_path)
        self.assertEqual(receipt["decision_count"], 2)
        self.assertTrue(receipt["review_complete"])
        self.assertFalse(receipt["canonical_write_allowed"])
        self.assertFalse(receipt["reviewer_identity_authenticated"])
        for path, data in originals.items():
            self.assertEqual(path.read_bytes(), data)

    def test_incomplete_decision_wrong_manifest_timestamp_or_changed_artifact_fails(self) -> None:
        template = build_entity_preview_review_template(manifest_json=self.manifest)
        decisions = template["decisions"][:1]
        decisions[0].update({"decision": "accept_candidate", "reviewer": "reviewer:test",
                             "reviewed_at": "2026-11-07T20:00:00+01:00"})
        path = self.write("partial.json", {**template, "decisions": decisions})
        with self.assertRaisesRegex(ValueError, "cover every candidate"):
            build_entity_preview_review_receipt(manifest_json=self.manifest, decisions_json=path)
        decisions = template["decisions"]
        for item in decisions:
            item.update({"decision": "accept_candidate", "reviewer": "reviewer:test", "reviewed_at": "2026-11-07T20:00:00"})
        path = self.write("bad-time.json", {**template, "decisions": decisions})
        with self.assertRaisesRegex(ValueError, "timezone"):
            build_entity_preview_review_receipt(manifest_json=self.manifest, decisions_json=path)
        self.updates.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            build_entity_preview_review_template(manifest_json=self.manifest)

    def test_cli_writes_new_template_and_receipt_without_overwriting(self) -> None:
        template_path, receipt_path = self.root / "template.json", self.root / "receipt.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["documents", "preview-review-template", "--manifest", str(self.manifest),
                                   "--output", str(template_path)]), 0)
        template = json.loads(template_path.read_text(encoding="utf-8"))
        for item in template["decisions"]:
            item.update({"decision": "needs_more_evidence", "reviewer": "reviewer:test",
                         "reviewed_at": "2026-11-07T20:00:00+01:00"})
        decisions = self.write("decisions.json", template)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["documents", "preview-review-record", "--manifest", str(self.manifest),
                                   "--decisions-json", str(decisions), "--output", str(receipt_path)]), 0)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertFalse(receipt["apply_allowed"])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["documents", "preview-review-record", "--manifest", str(self.manifest),
                                   "--decisions-json", str(decisions), "--output", str(receipt_path)]), 1)

    def test_historical_event_preview_targets_use_event_link_artifact(self) -> None:
        event_links = self.write("event-links.json", {"@type": "CandidateDocumentEventLinkSet",
            "candidate_document_event_links": [{"@id": "candidate-event-link:1", "source_document_id": "doc:2"}]})
        event_updates = self.write("event-updates.json", {"@type": "CandidateEventUpdateSet",
            "candidate_updates": [{"@id": "candidate-event-update:1", "source_document_ids": ["doc:2"]}]})
        event_manifest = self.write("event-manifest.json", {"@type": "HistoricalEventPreviewManifest",
            "preview_only": True, "requires_human_review": True,
            "artifacts": {"event_links": self.ref(event_links), "event_updates": self.ref(event_updates)}})
        template = build_entity_preview_review_template(manifest_json=event_manifest)
        self.assertEqual(template["preview_type"], "HistoricalEventPreviewManifest")
        self.assertEqual({item["candidate_id"] for item in template["decisions"]},
                         {"candidate-event-link:1", "candidate-event-update:1"})

    def test_wizard_collects_decisions_and_creates_receipt_payload_without_json_file(self) -> None:
        responses = iter(["reviewer:test", "a", "checked source", "r", "conflict", "s"])
        captured = []
        fixed_time = datetime(2026, 11, 7, 21, 0, tzinfo=timezone.utc)
        payload = run_entity_preview_review_wizard(
            manifest_json=self.manifest, input_fn=lambda prompt: next(responses),
            output_fn=captured.append, now_fn=lambda: fixed_time,
        )
        rendered = "\n".join(captured)
        self.assertIn("evidence_span=a Purocielo", rendered)
        self.assertIn("candidate_value: Purocielo", rendered)
        self.assertIsNotNone(payload)
        self.assertEqual([item["decision"] for item in payload["decisions"]], ["accept_candidate", "reject_candidate"])
        self.assertTrue(all(item["reviewed_at"].endswith("+00:00") for item in payload["decisions"]))
        receipt = build_entity_preview_review_receipt_from_decisions(manifest_json=self.manifest, decisions_payload=payload)
        self.assertEqual(receipt["decisions_source"]["method"], "interactive_cli_wizard")
        self.assertFalse(receipt["canonical_write_allowed"])
        self.assertFalse((self.root / "decisions.json").exists())

    def test_wizard_abort_or_missing_final_confirmation_returns_no_decisions(self) -> None:
        aborted = run_entity_preview_review_wizard(
            manifest_json=self.manifest, input_fn=lambda prompt: "reviewer:test" if "reviewer" in prompt else "q",
            output_fn=lambda value: None,
        )
        self.assertIsNone(aborted)
        responses = iter(["reviewer:test", "a", "", "a", "", "n"])
        not_confirmed = run_entity_preview_review_wizard(
            manifest_json=self.manifest, input_fn=lambda prompt: next(responses), output_fn=lambda value: None,
        )
        self.assertIsNone(not_confirmed)

    def test_cli_wizard_writes_receipt_from_terminal_decisions_without_decision_json(self) -> None:
        template = build_entity_preview_review_template(manifest_json=self.manifest)
        decisions = []
        for index, item in enumerate(template["decisions"]):
            decisions.append({**item, "decision": "accept_candidate", "reviewer": "reviewer:test",
                              "reviewed_at": f"2026-11-07T21:0{index}:00+00:00", "note": "terminal fixture"})
        payload = {"@type": "EntityPreviewHumanReviewDecisionSet", "preview_manifest": template["preview_manifest"],
                   "preview_type": template["preview_type"], "decisions": decisions}
        output = self.root / "wizard-receipt.json"
        with patch("caduti_fonti_report.memoria_cli.sys.stdin.isatty", return_value=True), \
             patch("caduti_fonti_report.memoria_cli.run_entity_preview_review_wizard", return_value=payload):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["documents", "preview-review-wizard", "--manifest", str(self.manifest),
                                       "--output", str(output)]), 0)
        receipt = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(receipt["decisions_source"]["method"], "interactive_cli_wizard")
        self.assertFalse(receipt["canonical_write_allowed"])
        self.assertFalse((self.root / "wizard-decisions.json").exists())


if __name__ == "__main__":
    unittest.main()
