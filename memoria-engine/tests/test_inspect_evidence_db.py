from __future__ import annotations

import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.inspect_evidence_db import (
    build_evidence_coverage,
    build_evidence_imports,
    build_evidence_records,
    build_evidence_subjects,
    build_documents,
    build_run_detail,
    build_runs,
    build_sources,
    build_summary,
    inspect_database,
)
from caduti_fonti_report.models import PersonQuery, SearchRun, SourceDocument, SourceResult
from caduti_fonti_report.sqlite_store import SQLiteEvidenceStore


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


def populated_store(db_path: Path) -> SQLiteEvidenceStore:
    store = SQLiteEvidenceStore(db_path)
    store.init_schema()
    run = SearchRun(
        run_id="meta:prova-cwgc",
        timestamp="2026-04-26T16:55:03+00:00",
        input_file="risultati/prova_meta_cwgc.json",
        source_ids=["cwgc"],
    )
    store.insert_search_run(run)
    store.insert_person_query(run.run_id, PersonQuery(full_name="Panov Sergio", given_name="Sergio", family_name="Panov"))
    store.insert_source_result(
        run.run_id,
        SourceResult(
            source_id="cwgc",
            source_name="CWGC",
            status="search_url_ready",
            note="URL pronti",
            query="Panov Sergio",
            search_url="https://example.test/cwgc",
        ),
    )
    store.insert_source_document(
        run.run_id,
        SourceDocument(
            document_id="cwgc-doc-1",
            source_id="cwgc",
            title="CWGC ricerca 1",
            url="https://example.test/cwgc/1",
            access_date="2026-04-26T16:55:03+00:00",
            media_type="text/uri-list",
        ),
    )
    store.insert_source_document(
        run.run_id,
        SourceDocument(
            document_id="cwgc-doc-2",
            source_id="cwgc",
            title="CWGC ricerca 2",
            url="https://example.test/cwgc/2",
            access_date="2026-04-26T16:55:03+00:00",
            media_type="text/uri-list",
        ),
    )
    store.insert_evidence_import_batch(
        {
            "import_batch_id": "evidence-import:mvp-run:abc123",
            "source_run_id": "mvp-run-pipeline",
            "imported_at": "2026-06-13T10:00:00+00:00",
            "source_run_dir": "P:/Comune/Me.Mo.Ri.a/risultati/runs/mvp-run-pipeline",
            "record_count": 4,
            "payload_hash": "batch-hash",
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:claim-1",
            "import_batch_id": "evidence-import:mvp-run:abc123",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "candidate_evidence_claim",
            "subject_id": "person:purocielo:bagni-alfonso",
            "source_document_id": "source-document:doc-1",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-1",
            "payload": {"@type": "CandidateEvidenceClaim"},
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:decision-1",
            "import_batch_id": "evidence-import:mvp-run:abc123",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "review_decision",
            "subject_id": "person:purocielo:bagni-alfonso",
            "source_document_id": "source-document:doc-1",
            "review_status": "pending",
            "payload_hash": "record-hash-2",
            "payload": {"@type": "MvpReviewDecision"},
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:workflow-1",
            "import_batch_id": "evidence-import:mvp-run:abc123",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "review_queue_item",
            "subject_id": "",
            "source_document_id": "",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-3",
            "payload": {"@type": "ReviewQueueItem", "subject_kind": "workflow"},
        }
    )
    store.insert_evidence_record(
        {
            "record_id": "evidence-record:entity-1",
            "import_batch_id": "evidence-import:mvp-run:abc123",
            "source_run_id": "mvp-run-pipeline",
            "record_kind": "extracted_entity",
            "subject_id": "",
            "source_document_id": "source-document:doc-2",
            "review_status": "unreviewed",
            "payload_hash": "record-hash-4",
            "payload": {"@type": "ExtractedEntity"},
        }
    )
    return store


class InspectEvidenceDbTests(unittest.TestCase):
    def test_summary_shows_table_counts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_summary(store))

        self.assertIn("search_runs: 1", text)
        self.assertIn("person_queries: 1", text)
        self.assertIn("source_results: 1", text)
        self.assertIn("source_documents: 2", text)
        self.assertIn("evidence_claims: 0", text)
        self.assertIn("evidence_import_batches: 1", text)
        self.assertIn("evidence_records: 4", text)

    def test_runs_are_listed_with_counts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_runs(store))

        self.assertIn("run_id=meta:prova-cwgc", text)
        self.assertIn("sources=cwgc", text)
        self.assertIn("source_documents=2", text)

    def test_run_detail_shows_single_run_counts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_run_detail(store, run_id="meta:prova-cwgc"))

        self.assertIn("run_id: meta:prova-cwgc", text)
        self.assertIn("sources: cwgc", text)
        self.assertIn("person_queries: 1", text)
        self.assertIn("source_results: 1", text)
        self.assertIn("source_documents: 2", text)
        self.assertIn("evidence_claims: 0", text)

    def test_documents_view_lists_document_identity_and_url(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_documents(store))

        self.assertIn("document_id=cwgc-doc-1", text)
        self.assertIn("source_id=cwgc", text)
        self.assertIn("title=CWGC ricerca 1", text)
        self.assertIn("url=https://example.test/cwgc/1", text)

    def test_sources_view_groups_by_source_and_status(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_sources(store))

        self.assertIn("source_id=cwgc | status=search_url_ready | count=1", text)

    def test_evidence_imports_view_lists_append_only_batches(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_evidence_imports(store))

        self.assertIn("import_batch_id=evidence-import:mvp-run:abc123", text)
        self.assertIn("source_run_id=mvp-run-pipeline", text)
        self.assertIn("records=4", text)
        self.assertIn("payload_hash=batch-hash", text)

    def test_evidence_records_view_groups_by_kind_and_status(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_evidence_records(store))

        self.assertIn("record_kind=candidate_evidence_claim | review_status=unreviewed | count=1", text)
        self.assertIn("record_kind=extracted_entity | review_status=unreviewed | count=1", text)
        self.assertIn("record_kind=review_decision | review_status=pending | count=1", text)
        self.assertIn("record_kind=review_queue_item | review_status=unreviewed | count=1", text)

    def test_evidence_subjects_view_groups_by_subject(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_evidence_subjects(store))

        self.assertIn("subject_id=person:purocielo:bagni-alfonso", text)
        self.assertIn("records=2", text)
        self.assertIn("source_documents=1", text)

    def test_evidence_coverage_distinguishes_subject_document_and_workflow_scope(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            store = populated_store(tmp_dir / "evidence.sqlite")
            text = "\n".join(build_evidence_coverage(store))

        self.assertIn("Evidence coverage by kind", text)
        self.assertIn("record_kind=candidate_evidence_claim | total=1 | with_subject=1 | with_source_document=1", text)
        self.assertIn("record_kind=extracted_entity | total=1 | with_subject=0 | with_source_document=1", text)
        self.assertIn("record_kind=review_queue_item | total=1 | with_subject=0 | with_source_document=0 | workflow_unscoped=1", text)

    def test_default_inspection_shows_summary_and_recent_runs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            populated_store(tmp_dir / "evidence.sqlite")
            text = inspect_database(db_path=tmp_dir / "evidence.sqlite")

        self.assertIn("Database summary", text)
        self.assertIn("Recent runs", text)
        self.assertIn("meta:prova-cwgc", text)

    def test_selected_evidence_views_are_rendered_together(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            populated_store(tmp_dir / "evidence.sqlite")
            text = inspect_database(
                db_path=tmp_dir / "evidence.sqlite",
                evidence_imports=True,
                evidence_records=True,
                evidence_subjects=True,
                evidence_coverage=True,
            )

        self.assertIn("Evidence import batches", text)
        self.assertIn("Evidence records by run, kind and status", text)
        self.assertIn("Evidence records by subject", text)
        self.assertIn("Evidence coverage by kind", text)


if __name__ == "__main__":
    unittest.main()
