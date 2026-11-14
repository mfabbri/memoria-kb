from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.candidate_entity_relationships import (  # noqa: E402
    build_candidate_entity_relationships,
)


@contextmanager
def workspace_temp_dir():
    base = Path(__file__).resolve().parents[1] / ".tmp-tests"
    base.mkdir(exist_ok=True)
    root = base / f"entity-relationships-{uuid.uuid4().hex}"
    root.mkdir()
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def link(*, kind: str, target_key: str, target_id: str, link_id: str, evidence_id: str,
         context: str, warnings: list[str] | None = None) -> dict:
    return {
        "@type": f"CandidateDocument{kind.title()}Link",
        "@id": link_id,
        target_key: target_id,
        "source_id": "source:fixture",
        "source_document_id": "document:fixture",
        "mention_id": evidence_id,
        "chunk_id": "chunk:fixture:1",
        "weak_segment_id": "segment:fixture:1",
        "context": context,
        "review_status": "unreviewed",
        "warnings": warnings or [],
    }


def fixtures(root: Path) -> tuple[Path, Path, Path]:
    person = write_json(root / "person.json", {
        "@type": "CandidateDocumentPersonLinkSet",
        "candidate_document_person_links": [link(kind="person", target_key="profile_id", target_id="person:fixture",
                                                   link_id="person-link:1", evidence_id="mention:person:1",
                                                   context="Persona Sintetica nella fonte (fixture).")],
    })
    place = write_json(root / "place.json", {
        "@type": "CandidateDocumentPlaceLinkSet",
        "candidate_document_place_links": [
            link(kind="place", target_key="place_id", target_id="place:fixture:a", link_id="place-link:a",
                 evidence_id="mention:place:1", context="presso Luogo Sintetico (fixture)."),
            link(kind="place", target_key="place_id", target_id="place:fixture:b", link_id="place-link:b",
                 evidence_id="mention:place:1", context="presso Luogo Sintetico (fixture)."),
        ],
    })
    event = write_json(root / "event.json", {
        "@type": "CandidateDocumentEventLinkSet",
        "candidate_document_event_links": [link(kind="event", target_key="event_id", target_id="event:fixture",
                                                  link_id="event-link:1", evidence_id="mention:event:1",
                                                  context="Evento Sintetico (fixture).",
                                                  warnings=["event_link_not_person_participation"])],
    })
    return person, place, event


class CandidateEntityRelationshipsTests(unittest.TestCase):
    def build(self, root: Path, inputs: tuple[Path, Path, Path], output: Path | None = None) -> dict:
        person, place, event = inputs
        return build_candidate_entity_relationships(person_links_json=person, place_links_json=place,
                                                    event_links_json=event, output_dir=output or root / "preview")

    def test_composes_typed_source_and_evidence_provenance_without_asserting_facts(self) -> None:
        with workspace_temp_dir() as root:
            result = self.build(root, fixtures(root))
            self.assertEqual(result["@type"], "CandidateEntityRelationshipSet")
            self.assertEqual(result["relationship_count"], 4)
            self.assertEqual(result["source_document_count"], 1)
            self.assertFalse(result["source_document_existence_verified"])
            self.assertFalse(result["historical_fact_asserted"])
            self.assertFalse(result["canonical_write_allowed"])
            relations = result["candidate_relationships"]
            self.assertEqual({item["relation_kind"] for item in relations},
                             {"identity_match_candidate", "place_mention_candidate", "event_mention_candidate"})
            self.assertEqual({item["target_entity_type"] for item in relations},
                             {"PersonResearchProfile", "Place", "HistoricalEvent"})
            self.assertEqual(sum(item["target_entity_type"] == "Place" for item in relations), 2)
            for item in relations:
                self.assertEqual(item["subject_entity_type"], "SourceDocumentReference")
                self.assertEqual(item["source_document_id"], "document:fixture")
                self.assertEqual(item["review_status"], "unreviewed")
                self.assertTrue(item["evidence"]["link_set"]["sha256"])
                self.assertTrue(item["evidence"]["text"])
            event_relation = next(item for item in relations if item["target_entity_type"] == "HistoricalEvent")
            self.assertIn("event_mention_does_not_assert_person_participation", event_relation["warnings"])
            self.assertIn("historical_fact_not_asserted", event_relation["warnings"])

    def test_identical_retry_is_idempotent_and_conflicting_places_are_preserved(self) -> None:
        with workspace_temp_dir() as root:
            inputs = fixtures(root)
            output = root / "preview"
            first = self.build(root, inputs, output)
            before = {path.name: path.read_bytes() for path in output.iterdir()}
            second = self.build(root, inputs, output)
            self.assertEqual(first, second)
            self.assertEqual(before, {path.name: path.read_bytes() for path in output.iterdir()})
            place_targets = [item["target_entity_id"] for item in second["candidate_relationships"]
                             if item["target_entity_type"] == "Place"]
            self.assertEqual(place_targets, ["place:fixture:a", "place:fixture:b"])

    def test_rejects_invalid_or_reviewed_link_before_output(self) -> None:
        with workspace_temp_dir() as root:
            inputs = fixtures(root)
            person = json.loads(inputs[0].read_text(encoding="utf-8"))
            person["candidate_document_person_links"][0]["review_status"] = "accepted"
            write_json(inputs[0], person)
            output = root / "preview"
            with self.assertRaisesRegex(ValueError, "must remain unreviewed"):
                self.build(root, inputs, output)
            self.assertFalse(output.exists())

    def test_installed_cli_creates_preview_for_person_place_event_fixtures(self) -> None:
        with workspace_temp_dir() as root:
            person, place, event = fixtures(root)
            launcher = Path(sys.executable).parent / ("memoria.exe" if sys.platform == "win32" else "memoria")
            output = root / "cli-preview"
            completed = subprocess.run([
                str(launcher), "documents", "relationship-preview",
                "--person-links-json", str(person), "--place-links-json", str(place),
                "--event-links-json", str(event), "--output-dir", str(output),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads((output / "candidate_entity_relationships.json").read_text(encoding="utf-8"))
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["relationship_count"], 4)
            self.assertEqual(manifest["relationship_count"], 4)
            self.assertTrue((output / "candidate_entity_relationships.md").is_file())


if __name__ == "__main__":
    unittest.main()
