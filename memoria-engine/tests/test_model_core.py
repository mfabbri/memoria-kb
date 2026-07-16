from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.models import (
    Caduto,
    EvidenceClaim,
    HistoricalEvent,
    Place,
    ResearchReport,
    SearchRun,
    SourceDocument,
    historical_event_from_jsonld,
    historical_event_to_jsonld,
    person_query_from_caduto,
    place_from_jsonld,
    place_to_jsonld,
    to_json_safe,
)


class CoreModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.caduto = Caduto(
            intestazione_pdf="ANDREOLI DINO",
            nome="Andreoli Dino",
            origine_sulla_lapide="Italia",
            nascita="17 maggio 1920, San Lazzaro di Savena",
            morte="11 ottobre 1944, Purocielo",
            ruolo_affiliazione="partigiano, 36a Brigata Garibaldi",
            fonti_richiamate="Lapide; CSV interno",
            profilo_biografico="Profilo breve",
            episodio_documentato="Battaglia di Purocielo",
        )

    def test_person_query_from_caduto_preserves_identity_and_metadata(self) -> None:
        query = person_query_from_caduto(self.caduto)

        self.assertEqual(query.full_name, "Andreoli Dino")
        self.assertEqual(query.family_name, "Andreoli")
        self.assertEqual(query.given_name, "Dino")
        self.assertEqual(query.birth_date, self.caduto.nascita)
        self.assertEqual(query.death_date, self.caduto.morte)
        self.assertEqual(query.formation, self.caduto.ruolo_affiliazione)
        self.assertEqual(query.event_hint, self.caduto.episodio_documentato)
        self.assertEqual(query.place_hint, self.caduto.origine_sulla_lapide)
        self.assertEqual(query.metadata["fonti_richiamate"], self.caduto.fonti_richiamate)
        self.assertEqual(set(query.metadata.keys()), set(self.caduto.__dict__.keys()))

    def test_person_query_from_caduto_handles_mononym_conservatively(self) -> None:
        caduto = Caduto(
            intestazione_pdf="GIORGIO",
            nome="Giorgio",
            origine_sulla_lapide="U.R.S.S.",
            nascita="non reperito",
            morte="non reperito",
            ruolo_affiliazione="partigiano sovietico",
            fonti_richiamate="",
            profilo_biografico="",
            episodio_documentato="",
        )

        query = person_query_from_caduto(caduto)

        self.assertEqual(query.full_name, "Giorgio")
        self.assertEqual(query.given_name, "Giorgio")
        self.assertEqual(query.family_name, "")

    def test_source_document_can_represent_reference_only_document(self) -> None:
        document = SourceDocument(
            document_id="doc:tna_wo417:andreoli-dino",
            source_id="tna_wo417",
            title="TNA Discovery reference",
            url="https://discovery.nationalarchives.gov.uk/",
            access_date="2026-04-26",
            media_type="text/uri-list",
            metadata={"access_mode": "reference_only", "reason": "needs_credentials"},
        )

        payload = to_json_safe(document)

        self.assertEqual(payload["metadata"]["access_mode"], "reference_only")
        json.dumps(payload)

    def test_evidence_claim_defaults_to_unreviewed_and_serializes(self) -> None:
        claim = EvidenceClaim(
            claim_id="claim:1",
            subject_id="person:andreoli-dino",
            field="formation.name",
            value="36a Brigata Garibaldi",
            source_document_id="doc:1",
            source_url="file:///archivi/storia.sba.unibo.it/Bologna.xls",
            extraction_method="local_excel_row",
            confidence=0.8,
        )

        payload = to_json_safe(claim)

        self.assertEqual(payload["review_status"], "unreviewed")
        self.assertEqual(payload["confidence"], 0.8)
        json.dumps(payload)

    def test_historical_event_serializes_to_jsonld_without_participants(self) -> None:
        event = HistoricalEvent(
            event_id="event:battaglia-purocielo",
            event_type="battle",
            label="Battaglia di Purocielo",
            description="Evento pilota non ancora revisionato.",
            place_labels=["Purocielo"],
            place_ids=["place:purocielo"],
            review_status="draft",
            provenance="fixture:manual",
        )

        payload = historical_event_to_jsonld(event)
        loaded = historical_event_from_jsonld(payload)

        self.assertEqual(payload["@type"], "HistoricalEvent")
        self.assertEqual(payload["@id"], "event:battaglia-purocielo")
        self.assertEqual(payload["review_status"], "draft")
        self.assertEqual(payload["provenance"], "fixture:manual")
        self.assertNotIn("participants", payload)
        self.assertEqual(loaded.event_id, "event:battaglia-purocielo")
        self.assertEqual(loaded.place_labels, ["Purocielo"])
        self.assertEqual(loaded.place_ids, ["place:purocielo"])
        json.dumps(payload)

    def test_historical_event_fixture_is_loadable_and_prudent(self) -> None:
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "events" / "battaglia-purocielo.jsonld"

        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        event = historical_event_from_jsonld(payload)

        self.assertEqual(event.event_id, "event:battaglia-purocielo")
        self.assertEqual(event.event_type, "battle")
        self.assertEqual(event.label, "Battaglia di Purocielo")
        self.assertEqual(event.review_status, "draft")
        self.assertEqual(event.place_ids, [])
        self.assertEqual(event.source_document_ids, [])
        self.assertEqual(event.evidence_claim_ids, [])
        self.assertNotIn("participants", payload)

    def test_place_serializes_to_jsonld_with_review_and_provenance(self) -> None:
        place = Place(
            place_id="place:purocielo",
            preferred_label="Purocielo",
            place_type="locality",
            alternate_labels=["Puro Cielo"],
            review_status="draft",
            provenance="fixture:manual",
        )

        payload = place_to_jsonld(place)
        loaded = place_from_jsonld(payload)

        self.assertEqual(payload["@type"], "Place")
        self.assertEqual(payload["@id"], "place:purocielo")
        self.assertEqual(payload["review_status"], "draft")
        self.assertEqual(payload["provenance"], "fixture:manual")
        self.assertEqual(payload["same_as"], [])
        self.assertIsNone(payload["latitude"])
        self.assertIsNone(payload["longitude"])
        self.assertEqual(loaded.place_id, "place:purocielo")
        self.assertEqual(loaded.alternate_labels, ["Puro Cielo"])
        json.dumps(payload)

    def test_place_fixtures_are_loadable_and_prudent(self) -> None:
        fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "places"

        for filename, expected_id in [
            ("purocielo.jsonld", "place:purocielo"),
            ("ca-di-malanca.jsonld", "place:ca-di-malanca"),
        ]:
            payload = json.loads((fixtures_dir / filename).read_text(encoding="utf-8"))
            place = place_from_jsonld(payload)

            self.assertEqual(place.place_id, expected_id)
            self.assertEqual(place.review_status, "draft")
            self.assertEqual(place.source_document_ids, [])
            self.assertEqual(place.evidence_claim_ids, [])
            self.assertEqual(place.same_as, [])
            self.assertIsNone(place.latitude)
            self.assertIsNone(place.longitude)
            self.assertNotIn("participants", payload)
            self.assertNotIn("memberships", payload)

    def test_research_report_serializes_nested_models_and_datetime(self) -> None:
        run = SearchRun(
            run_id="run:test",
            timestamp=datetime(2026, 4, 26, 12, 0, tzinfo=UTC).isoformat(),
            input_file="ricerche/caduti_purocielo.csv",
            source_ids=["storia_memoria_bo_excel"],
            parameters={"limit": "1"},
        )
        report = ResearchReport(
            run=run,
            person_queries=[person_query_from_caduto(self.caduto)],
            source_documents=[
                SourceDocument(document_id="doc:1", source_id="storia_memoria_bo_excel")
            ],
            evidence_claims=[
                EvidenceClaim(
                    claim_id="claim:1",
                    subject_id="person:andreoli-dino",
                    field="death.place",
                    value="Purocielo",
                )
            ],
        )

        payload = to_json_safe({"report": report, "checked_at": datetime(2026, 4, 26, 12, 30, tzinfo=UTC)})

        self.assertEqual(payload["report"]["run"]["run_id"], "run:test")
        self.assertEqual(payload["report"]["person_queries"][0]["full_name"], "Andreoli Dino")
        self.assertEqual(payload["checked_at"], "2026-04-26T12:30:00+00:00")
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
