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

from caduti_fonti_report.document_analysis.local_processing_runner import run_local_document_processing  # noqa: E402
from caduti_fonti_report.document_analysis import local_processing_runner  # noqa: E402
from caduti_fonti_report.document_analysis.local_processing_progress import ProgressReporter, progress_item  # noqa: E402


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


def write_raw_text_document(root_dir: Path) -> Path:
    source_dir = root_dir / "camalanca_html"
    source_dir.mkdir(parents=True)
    raw_path = source_dir / "andreoli-dino.txt"
    raw_path.write_text(
        "Andreoli Dino opero a Purocielo nella 36a Brigata Garibaldi. "
        "Il 17 maggio 1920 e' indicato come data da verificare. "
        "Una nota cita la 26. Panzer-Division come contesto militare da revisionare.",
        encoding="utf-8",
    )
    return raw_path


class LocalProcessingProgressTests(unittest.TestCase):
    def test_progress_item_reads_current_count(self):
        self.assertEqual(progress_item("OCR 12/40 file=x"), 12)
        self.assertEqual(progress_item("documents=7/9"), 7)
        self.assertEqual(progress_item("no numeric token"), 0)

    def test_reporter_honors_force_item_and_time_thresholds(self):
        now = [100.0]
        messages: list[str] = []
        reporter = ProgressReporter(messages.append, item_interval=5, seconds_interval=10, clock=lambda: now[0])

        reporter.report("item 1/20")
        reporter.report("item 5/20")
        reporter.report("item 6/20")
        now[0] += 10
        reporter.report("item 7/20")
        reporter.report("item 8/20", force=True)

        self.assertEqual(messages, ["item 5/20", "item 7/20", "item 8/20"])

    def test_reporter_without_callback_is_noop(self):
        ProgressReporter(None).report("item 1/2", force=True)


def write_raw_image_document(root_dir: Path) -> Path:
    source_dir = root_dir / "foto"
    source_dir.mkdir(parents=True)
    raw_path = source_dir / "scansione.jpg"
    raw_path.write_bytes(b"fake-image-bytes")
    return raw_path


def write_raw_csv_document(root_dir: Path) -> Path:
    source_dir = root_dir / "legacy_documents"
    source_dir.mkdir(parents=True)
    raw_path = source_dir / "caduti_purocielo.csv"
    raw_path.write_text(
        "nome,nascita,morte,ruolo_affiliazione\n"
        "Andreoli Dino,17 maggio 1920,11 ottobre 1944,36a Brigata Garibaldi\n",
        encoding="utf-8-sig",
    )
    return raw_path


def write_research_glossary(root_dir: Path) -> Path:
    research_dir = root_dir / "remote" / "ricerche"
    glossary_dir = research_dir / "military_glossaries"
    glossary_dir.mkdir(parents=True)
    glossary = {
        "@type": "MilitaryGlossary",
        "@id": "military-glossary:test.remote",
        "name": "Glossario test remoto",
        "language": "it",
        "review_status": "unreviewed",
        "entries": [
            {
                "@type": "MilitaryGlossaryEntry",
                "@id": "military-glossary-entry:test:brigata",
                "term": "Brigata",
                "language": "it",
                "category": "unit_type",
                "translation_it": "brigata",
                "aliases": [],
                "abbreviations": [],
                "source_reference": "test_remote_glossary",
                "review_status": "unreviewed",
            }
        ],
    }
    (glossary_dir / "test-glossary.jsonld").write_text(json.dumps(glossary, ensure_ascii=False, indent=2), encoding="utf-8")
    return research_dir


def statuses_by_name(manifest: dict[str, object]) -> dict[str, str]:
    steps = manifest.get("steps", [])
    assert isinstance(steps, list)
    return {str(step.get("name", "")): str(step.get("status", "")) for step in steps if isinstance(step, dict)}


class LocalDocumentProcessingRunnerTests(unittest.TestCase):
    def test_local_processing_writes_manifest_and_preview_outputs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            write_raw_text_document(root_dir)

            manifest = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )

            run_dir = results_dir / "runs" / "local-delta"
            manifest_path = run_dir / "manifest.json"
            summary_path = run_dir / "run_summary.md"
            log_path = run_dir / "run.log"
            feedback_path = run_dir / "document_analysis" / "research_feedback_actions.json"
            candidate_profiles_path = run_dir / "document_analysis" / "candidate_person_profiles_from_documents.json"
            military_path = run_dir / "document_analysis" / "military_glossary_mentions.json"
            mentions_path = run_dir / "document_analysis" / "document_mentions.json"
            language_path = run_dir / "document_analysis" / "document_language_assessments.json"
            language_routing_path = run_dir / "document_analysis" / "document_language_routing.json"
            input_plan_path = run_dir / "document_analysis" / "input_processing_plan.json"
            image_preprocessing_plan_path = run_dir / "document_analysis" / "image_preprocessing_plan.json"
            map_catalog_path = run_dir / "document_analysis" / "historical_map_catalog.json"
            summary_exists = summary_path.exists()
            log_text = log_path.read_text(encoding="utf-8")
            feedback_exists = feedback_path.exists()
            candidate_profiles_exists = candidate_profiles_path.exists()
            military_exists = military_path.exists()
            language_exists = language_path.exists()
            language_routing_exists = language_routing_path.exists()
            input_plan_exists = input_plan_path.exists()
            image_preprocessing_plan_exists = image_preprocessing_plan_path.exists()
            map_catalog_exists = map_catalog_path.exists()
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
            military = json.loads(military_path.read_text(encoding="utf-8"))
            mentions = json.loads(mentions_path.read_text(encoding="utf-8"))
            language = json.loads(language_path.read_text(encoding="utf-8"))
            language_routing = json.loads(language_routing_path.read_text(encoding="utf-8"))
            image_preprocessing_plan = json.loads(image_preprocessing_plan_path.read_text(encoding="utf-8"))
            map_catalog = json.loads(map_catalog_path.read_text(encoding="utf-8"))
            language_sidecar_exists = any(processed_dir.rglob("*.language.json"))
            language_routing_sidecar_exists = any(processed_dir.rglob("*.language-routing.json"))

        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(persisted["@type"], "LocalDocumentProcessingRunManifest")
        self.assertEqual(persisted["outputs"]["run_log"], str(log_path))
        self.assertTrue(summary_exists)
        self.assertIn("RUN START local_document_processing", log_text)
        self.assertIn("SNAPSHOT START input_processing_plan", log_text)
        self.assertIn("SNAPSHOT END input_processing_plan", log_text)
        self.assertIn("STEP START input_processing_plan", log_text)
        self.assertIn("STEP PROGRESS input_processing_plan input_processing_plan inventory start", log_text)
        self.assertIn("STEP PROGRESS input_processing_plan inventory done", log_text)
        self.assertIn("STEP END input_processing_plan status=completed", log_text)
        self.assertIn("RUN END local_document_processing", log_text)
        self.assertTrue(feedback_exists)
        self.assertTrue(candidate_profiles_exists)
        self.assertTrue(military_exists)
        self.assertTrue(language_exists)
        self.assertTrue(language_routing_exists)
        self.assertTrue(input_plan_exists)
        self.assertTrue(image_preprocessing_plan_exists)
        self.assertTrue(map_catalog_exists)
        self.assertEqual(statuses_by_name(persisted)["input_processing_plan"], "completed")
        self.assertEqual(statuses_by_name(persisted)["image_preprocessing_plan"], "completed")
        self.assertEqual(statuses_by_name(persisted)["historical_map_catalog"], "completed")
        self.assertEqual(statuses_by_name(persisted)["metadata_extraction"], "completed")
        self.assertEqual(statuses_by_name(persisted)["document_language_detection"], "completed")
        self.assertEqual(statuses_by_name(persisted)["document_language_routing"], "completed")
        self.assertEqual(statuses_by_name(persisted)["candidate_person_profiles_from_documents"], "completed")
        self.assertEqual(statuses_by_name(persisted)["military_glossary_mentions"], "completed")
        self.assertEqual(statuses_by_name(persisted)["research_feedback_actions"], "completed")
        self.assertEqual(language["@type"], "DocumentLanguageAssessmentSet")
        self.assertGreaterEqual(language["assessment_count"], 1)
        self.assertEqual(language_routing["@type"], "DocumentLanguageRoutingPlanSet")
        self.assertGreaterEqual(language_routing["routing_count"], 1)
        self.assertEqual(image_preprocessing_plan["@type"], "ImagePreprocessingPlan")
        self.assertEqual(image_preprocessing_plan["image_count"], 0)
        self.assertEqual(military["@type"], "CandidateMilitaryGlossaryMentionSet")
        self.assertGreaterEqual(military["mention_count"], 1)
        self.assertEqual(map_catalog["@type"], "HistoricalMapCatalog")
        self.assertEqual(map_catalog["map_candidate_count"], 0)
        self.assertTrue(language_sidecar_exists)
        self.assertEqual(mentions["@type"], "DocumentMentionCandidateSet")
        self.assertEqual(feedback["@type"], "ResearchFeedbackActionSet")
        self.assertTrue(language_routing_sidecar_exists)
        self.assertNotIn("EvidenceClaim", json.dumps(persisted))
        self.assertNotIn("ProfilePatch", json.dumps(persisted))
        self.assertNotIn("verified_facts", json.dumps(persisted))
        self.assertNotIn("EvidenceClaim", json.dumps(language_routing))
        self.assertNotIn("ProfilePatch", json.dumps(language_routing))
        self.assertNotIn("verified_facts", json.dumps(language_routing))
        self.assertNotIn("CandidateTranslation", json.dumps(language_routing))
        self.assertNotIn('"@type": "MilitaryUnit"', json.dumps(military))
        self.assertNotIn("EvidenceClaim", json.dumps(military))
        self.assertNotIn("ProfilePatch", json.dumps(military))
        self.assertNotIn("verified_facts", json.dumps(military))

    def test_local_processing_builds_candidate_person_profiles_from_csv_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            write_raw_csv_document(root_dir)

            manifest = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-csv-candidate-profiles",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )
            document_dir = results_dir / "runs" / "local-csv-candidate-profiles" / "document_analysis"
            payload = json.loads((document_dir / "candidate_person_profiles_from_documents.json").read_text(encoding="utf-8"))
            markdown = (document_dir / "candidate_person_profiles_from_documents.md").read_text(encoding="utf-8")
            summary = (results_dir / "runs" / "local-csv-candidate-profiles" / "run_summary.md").read_text(encoding="utf-8")

        statuses = statuses_by_name(manifest)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(statuses["candidate_person_profiles_from_documents"], "completed")
        self.assertEqual(payload["@type"], "CandidatePersonProfileSet")
        self.assertEqual(payload["candidate_profile_count"], 1)
        self.assertEqual(payload["candidate_person_profiles"][0]["canonical_name"], "Andreoli Dino")
        self.assertEqual(payload["candidate_person_profiles"][0]["promotion_status"], "not_promoted")
        self.assertIn("Andreoli Dino", markdown)
        self.assertIn("candidate_profile_count=1", summary)
        self.assertNotIn("PersonResearchProfile", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_local_processing_records_input_snapshot_read_errors_without_failing(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            unreadable_path = write_raw_text_document(root_dir)
            original_sha256 = local_processing_runner._sha256_file

            def fake_sha256(path: Path) -> str:
                if path == unreadable_path:
                    raise OSError("lettura negata")
                return original_sha256(path)

            with patch("caduti_fonti_report.document_analysis.local_processing_runner._sha256_file", side_effect=fake_sha256):
                manifest = run_local_document_processing(
                    root_dir=root_dir,
                    processed_dir=processed_dir,
                    results_dir=results_dir,
                    run_id="local-input-read-error",
                    max_chars=80,
                    overlap_chars=10,
                    enable_llm_chunk_classification=False,
                )
            summary = (results_dir / "runs" / "local-input-read-error" / "run_summary.md").read_text(encoding="utf-8")

        input_step = [step for step in manifest["steps"] if step["name"] == "input_processing_plan"][0]
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(input_step["status"], "completed")
        self.assertEqual(input_step["input_read_error_count"], 1)
        self.assertIn("read_error", json.dumps(input_step["input_snapshot"]))
        self.assertIn("Errori lettura input: 1", summary)

    def test_local_processing_can_write_results_outside_default_results_dir(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            remote_results_dir = tmp_dir / "remote" / "Comune" / "Me.Mo.Ria" / "risultati"
            write_raw_text_document(root_dir)

            manifest = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=remote_results_dir,
                run_id="local-remote-results",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )

            manifest_path = remote_results_dir / "runs" / "local-remote-results" / "manifest.json"
            local_default_path = tmp_dir / "risultati" / "runs" / "local-remote-results" / "manifest.json"
            manifest_exists = manifest_path.exists()
            local_default_exists = local_default_path.exists()
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "completed")
        self.assertTrue(manifest_exists)
        self.assertFalse(local_default_exists)
        self.assertEqual(persisted["outputs"]["manifest_json"], str(manifest_path))

    def test_local_processing_derives_glossary_dir_from_research_dir(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            research_dir = write_research_glossary(tmp_dir)
            write_raw_text_document(root_dir)

            manifest = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                research_dir=research_dir,
                run_id="local-remote-research",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )

            manifest_path = results_dir / "runs" / "local-remote-research" / "manifest.json"
            military_path = results_dir / "runs" / "local-remote-research" / "document_analysis" / "military_glossary_mentions.json"
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            military = json.loads(military_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(persisted["inputs"]["research_dir"], str(research_dir))
        self.assertEqual(persisted["inputs"]["glossary_dir"], str(research_dir / "military_glossaries"))
        self.assertEqual(military["glossary_dir"], str(research_dir / "military_glossaries"))
        self.assertGreaterEqual(military["mention_count"], 1)

    def test_second_run_skips_cached_steps_when_inputs_are_unchanged(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            write_raw_text_document(root_dir)

            run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta-cache",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )
            second = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta-cache",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )

        statuses = statuses_by_name(second)
        self.assertEqual(second["status"], "completed")
        self.assertEqual(statuses["metadata_extraction"], "skipped_cached")
        self.assertEqual(statuses["input_processing_plan"], "skipped_cached")
        self.assertEqual(statuses["historical_map_catalog"], "skipped_cached")
        self.assertEqual(statuses["text_extraction"], "skipped_cached")
        self.assertEqual(statuses["candidate_person_profiles_from_documents"], "skipped_cached")
        self.assertEqual(statuses["document_language_detection"], "skipped_cached")
        self.assertEqual(statuses["document_language_routing"], "skipped_cached")
        self.assertEqual(statuses["military_glossary_mentions"], "skipped_cached")
        self.assertEqual(statuses["document_chunking"], "skipped_cached")
        self.assertEqual(statuses["ocr_batch"], "skipped_not_enabled")
        self.assertEqual(statuses["llm_chunk_classification"], "skipped_not_enabled")
        self.assertEqual(statuses["weak_document_segmentation"], "skipped_cached")
        self.assertEqual(statuses["document_mentions"], "skipped_cached")
        self.assertEqual(statuses["research_feedback_actions"], "skipped_cached")

    def test_summary_reports_added_inputs_between_runs(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            write_raw_text_document(root_dir)

            run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta-added",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )
            new_photo = root_dir / "foto" / "nuova-foto.jpg"
            new_photo.parent.mkdir()
            new_photo.write_bytes(b"fake-photo-bytes")
            second = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta-added",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )
            summary = (results_dir / "runs" / "local-delta-added" / "run_summary.md").read_text(encoding="utf-8")

        metadata_step = [step for step in second["steps"] if step["name"] == "metadata_extraction"][0]
        self.assertEqual(metadata_step["input_delta"]["status"], "changed")
        self.assertEqual(metadata_step["input_delta"]["added_count"], 1)
        self.assertTrue(any("nuova-foto.jpg" in path for path in metadata_step["input_delta"]["added"]))
        self.assertIn("Delta input: changed, aggiunti=1", summary)
        self.assertIn("nuova-foto.jpg", summary)

    def test_force_derived_regenerates_cached_steps(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            write_raw_text_document(root_dir)

            run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta-force",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=False,
            )
            forced = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta-force",
                force_derived=True,
                max_chars=80,
                overlap_chars=10,
                min_language_text_chars=10,
                enable_llm_chunk_classification=False,
            )

        statuses = statuses_by_name(forced)
        self.assertEqual(forced["status"], "completed")
        self.assertEqual(statuses["llm_chunk_classification"], "skipped_not_enabled")
        self.assertTrue(
            all(
                status == "completed"
                for name, status in statuses.items()
                if name not in {"llm_chunk_classification", "ocr_batch"}
            )
        )
        self.assertEqual(statuses["ocr_batch"], "skipped_not_enabled")

    def test_missing_input_is_audited_without_failure(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            manifest = run_local_document_processing(
                root_dir=tmp_dir / "missing-raw",
                processed_dir=tmp_dir / "processed",
                results_dir=tmp_dir / "risultati",
                run_id="local-delta-missing",
                enable_llm_chunk_classification=False,
            )

        statuses = statuses_by_name(manifest)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(statuses["metadata_extraction"], "skipped_missing_input")
        self.assertEqual(statuses["input_processing_plan"], "skipped_missing_input")
        self.assertEqual(statuses["historical_map_catalog"], "skipped_missing_input")
        self.assertEqual(statuses["text_extraction"], "completed")
        self.assertEqual(statuses["candidate_person_profiles_from_documents"], "completed")
        self.assertEqual(statuses["document_language_detection"], "completed")
        self.assertEqual(statuses["document_language_routing"], "completed")
        self.assertEqual(statuses["military_glossary_mentions"], "completed")
        self.assertEqual(statuses["document_chunking"], "completed")
        self.assertEqual(statuses["research_feedback_actions"], "completed")

    def test_language_detection_summary_count_is_reported(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            write_raw_text_document(root_dir)

            run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta-language",
                min_language_text_chars=10,
                enable_llm_chunk_classification=False,
            )
            summary = (results_dir / "runs" / "local-delta-language" / "run_summary.md").read_text(encoding="utf-8")
            manifest = json.loads((results_dir / "runs" / "local-delta-language" / "manifest.json").read_text(encoding="utf-8"))

        language_step = [step for step in manifest["steps"] if step["name"] == "document_language_detection"][0]
        routing_step = [step for step in manifest["steps"] if step["name"] == "document_language_routing"][0]
        self.assertEqual(language_step["summary"]["assessment_count"], 1)
        self.assertEqual(routing_step["summary"]["routing_count"], 1)
        self.assertIn("document_language_detection", summary)
        self.assertIn("document_language_routing", summary)
        self.assertIn("assessment_count=1", summary)
        self.assertIn("routing_count=1", summary)

    def test_ocr_is_skipped_by_default_and_force_ocr_does_not_enable_it(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            write_raw_text_document(root_dir)

            manifest = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=tmp_dir / "processed",
                results_dir=tmp_dir / "risultati",
                run_id="local-delta-ocr",
                force_ocr=True,
                enable_llm_chunk_classification=False,
            )

        statuses = statuses_by_name(manifest)
        ocr_step = [step for step in manifest["steps"] if step["name"] == "ocr_batch"][0]
        self.assertEqual(statuses["ocr_batch"], "skipped_not_enabled")
        self.assertEqual(ocr_step["reason"], "force_ocr_requires_run_ocr")
        self.assertEqual(manifest["status"], "completed")

    def test_run_ocr_executes_batch_inside_local_processing(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            write_raw_image_document(root_dir)

            fake_report = {
                "@type": "DocumentOcrBatchReport",
                "root_dir": str(root_dir),
                "output_dir": str(processed_dir),
                "preprocess_before_ocr": True,
                "enable_region_ocr": True,
                "summary": {
                    "total": 1,
                    "processed": 1,
                    "skipped_existing_text": 0,
                    "skipped_missing_sidecar": 0,
                    "skipped_sidecar_mismatch": 0,
                    "skipped_duplicate_output": 0,
                    "error": 0,
                },
                "documents": [
                    {
                        "status": "processed",
                        "file": str(root_dir / "foto" / "scansione.jpg"),
                        "ocr_preprocessing_status": "preprocessed_temporary",
                    }
                ],
            }

            with patch("caduti_fonti_report.document_analysis.local_processing_runner.run_document_ocr_batch", return_value=fake_report) as run_batch:
                manifest = run_local_document_processing(
                    root_dir=root_dir,
                    processed_dir=processed_dir,
                    results_dir=results_dir,
                    run_id="local-delta-run-ocr",
                    run_ocr=True,
                    force_ocr=True,
                    preprocess_before_ocr=True,
                    enable_region_ocr=True,
                    ocr_language="ita+deu",
                    page_segmentation_mode="4",
                    dpi="300",
                    ocr_max_workers=1,
                    ocr_progress_every=1,
                    enable_llm_chunk_classification=False,
                )

            report_path = results_dir / "runs" / "local-delta-run-ocr" / "document_analysis" / "ocr_batch_report.json"
            log_path = results_dir / "runs" / "local-delta-run-ocr" / "document_analysis" / "ocr_batch.log"
            report = json.loads(report_path.read_text(encoding="utf-8"))

        statuses = statuses_by_name(manifest)
        ocr_step = [step for step in manifest["steps"] if step["name"] == "ocr_batch"][0]
        self.assertEqual(statuses["ocr_batch"], "completed")
        self.assertEqual(ocr_step["summary"]["processed"], 1)
        self.assertEqual(manifest["inputs"]["ocr_progress_every"], 1)
        self.assertEqual(manifest["outputs"]["ocr_batch_log"], str(log_path))
        self.assertEqual(report["@type"], "DocumentOcrBatchReport")
        self.assertEqual(report["documents"][0]["ocr_preprocessing_status"], "preprocessed_temporary")
        run_batch.assert_called_once()
        kwargs = run_batch.call_args.kwargs
        self.assertEqual(kwargs["language"], "ita+deu")
        self.assertEqual(kwargs["page_segmentation_mode"], "4")
        self.assertEqual(kwargs["dpi"], "300")
        self.assertTrue(kwargs["preprocess_before_ocr"])
        self.assertTrue(kwargs["enable_region_ocr"])
        self.assertTrue(kwargs["overwrite"])
        self.assertEqual(kwargs["max_workers"], 1)
        self.assertEqual(kwargs["log_file"], log_path)
        self.assertEqual(kwargs["progress_every"], 1)
        self.assertIsNotNone(kwargs["progress_callback"])

    def test_llm_chunk_classification_is_skipped_by_default(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            write_raw_text_document(root_dir)

            with patch.dict("os.environ", {"CADUTI_LLM_CHUNK_ENABLED": "false"}, clear=False):
                manifest = run_local_document_processing(
                    root_dir=root_dir,
                    processed_dir=tmp_dir / "processed",
                    results_dir=tmp_dir / "risultati",
                    run_id="local-delta-llm-default",
                    max_chars=80,
                    overlap_chars=10,
                )
            llm_output_exists = any((tmp_dir / "risultati").rglob("llm_chunk_classifications.json"))

        step = [item for item in manifest["steps"] if item["name"] == "llm_chunk_classification"][0]
        self.assertEqual(step["status"], "skipped_not_enabled")
        self.assertEqual(step["reason"], "enable_llm_chunk_classification_false")
        self.assertFalse(llm_output_exists)

    def test_llm_chunk_classification_can_run_inside_wrapper(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            results_dir = tmp_dir / "risultati"
            write_raw_text_document(root_dir)

            manifest = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=results_dir,
                run_id="local-delta-llm-enabled",
                max_chars=80,
                overlap_chars=10,
                enable_llm_chunk_classification=True,
                llm_provider="fake",
                llm_model_name="fake-local-llm",
            )
            llm_path = results_dir / "runs" / "local-delta-llm-enabled" / "document_analysis" / "llm_chunk_classifications.json"
            summary = (results_dir / "runs" / "local-delta-llm-enabled" / "run_summary.md").read_text(encoding="utf-8")
            payload = json.loads(llm_path.read_text(encoding="utf-8"))

        step = [item for item in manifest["steps"] if item["name"] == "llm_chunk_classification"][0]
        self.assertEqual(step["status"], "completed")
        self.assertEqual(step["summary"]["classification_count"], payload["classification_count"])
        self.assertGreaterEqual(payload["classification_count"], 1)
        self.assertEqual(payload["@type"], "LLMChunkClassificationSet")
        self.assertEqual(payload["provider"], "fake")
        self.assertIn("classification_count=", summary)
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("ProfilePatch", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_llm_chunk_classification_defaults_can_come_from_environment(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            write_raw_text_document(root_dir)

            with patch.dict(
                "os.environ",
                {
                    "CADUTI_LLM_CHUNK_ENABLED": "true",
                    "CADUTI_LLM_CHUNK_PROVIDER": "fake",
                    "CADUTI_LLM_CHUNK_MODEL": "fake-env-model",
                    "CADUTI_LLM_CHUNK_PROMPT_VERSION": "chunk-classification-env-test",
                    "CADUTI_LLM_CHUNK_TIMEOUT_SECONDS": "17",
                },
                clear=False,
            ):
                manifest = run_local_document_processing(
                    root_dir=root_dir,
                    processed_dir=tmp_dir / "processed",
                    results_dir=tmp_dir / "risultati",
                    run_id="local-delta-llm-env",
                    max_chars=80,
                    overlap_chars=10,
                )

        inputs = manifest["inputs"]
        step = [item for item in manifest["steps"] if item["name"] == "llm_chunk_classification"][0]
        self.assertEqual(step["status"], "completed")
        self.assertTrue(inputs["enable_llm_chunk_classification"])
        self.assertEqual(inputs["llm_chunk_model_name"], "fake-env-model")
        self.assertEqual(inputs["llm_chunk_prompt_version"], "chunk-classification-env-test")
        self.assertEqual(inputs["llm_chunk_timeout_seconds"], 17)

    def test_image_only_run_does_not_chunk_or_classify_existing_processed_texts(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            root_dir = tmp_dir / "raw"
            processed_dir = tmp_dir / "processed"
            stale_dir = processed_dir / "stale-source"
            stale_dir.mkdir(parents=True)
            (stale_dir / "stale.text.json").write_text(
                json.dumps(
                    {
                        "@type": "ProcessedDocumentText",
                        "source_id": "stale-source",
                        "source_document_id": "stale-source:old",
                        "document_class": "html_document",
                        "review_status": "unreviewed",
                        "text_status": "extracted",
                        "text": "Andreoli Dino nella 36a Brigata Garibaldi.",
                        "text_sha256": "old",
                    }
                ),
                encoding="utf-8",
            )
            write_raw_image_document(root_dir)

            manifest = run_local_document_processing(
                root_dir=root_dir,
                processed_dir=processed_dir,
                results_dir=tmp_dir / "risultati",
                run_id="local-image-only",
                enable_llm_chunk_classification=True,
                llm_provider="fake",
            )
            document_dir = tmp_dir / "risultati" / "runs" / "local-image-only" / "document_analysis"
            summary = (tmp_dir / "risultati" / "runs" / "local-image-only" / "run_summary.md").read_text(encoding="utf-8")
            text_payload = json.loads((document_dir / "document_text_extraction.json").read_text(encoding="utf-8"))
            chunks_payload = json.loads((document_dir / "document_chunks.json").read_text(encoding="utf-8"))
            routing_payload = json.loads((document_dir / "document_language_routing.json").read_text(encoding="utf-8"))
            military_payload = json.loads((document_dir / "military_glossary_mentions.json").read_text(encoding="utf-8"))
            candidate_profiles_payload = json.loads((document_dir / "candidate_person_profiles_from_documents.json").read_text(encoding="utf-8"))
            llm_payload = json.loads((document_dir / "llm_chunk_classifications.json").read_text(encoding="utf-8"))

        statuses = statuses_by_name(manifest)
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(statuses["llm_chunk_classification"], "completed")
        self.assertEqual(text_payload["extracted_count"], 0)
        self.assertEqual(text_payload["extraction_status_counts"], {"manual_ocr_required": 1})
        self.assertEqual(text_payload["document_class_counts"], {"image_scan": 1})
        text_step = [item for item in manifest["steps"] if item["name"] == "text_extraction"][0]
        self.assertEqual(text_step["summary"]["extraction_status_counts"], {"manual_ocr_required": 1})
        self.assertIn("extraction_status_counts={manual_ocr_required: 1}", summary)
        self.assertIn("document_class_counts={image_scan: 1}", summary)
        self.assertEqual(routing_payload["routing_count"], 0)
        self.assertEqual(chunks_payload["document_count"], 0)
        self.assertEqual(chunks_payload["chunk_count"], 0)
        self.assertEqual(military_payload["document_count"], 0)
        self.assertEqual(military_payload["mention_count"], 0)
        self.assertEqual(candidate_profiles_payload["document_count"], 0)
        self.assertEqual(candidate_profiles_payload["candidate_profile_count"], 0)
        self.assertEqual(llm_payload["document_count"], 0)
        self.assertEqual(llm_payload["classification_count"], 0)
        self.assertNotIn("stale-source:old", json.dumps(chunks_payload))
        self.assertNotIn("stale-source:old", json.dumps(routing_payload))
        self.assertNotIn("stale-source:old", json.dumps(military_payload))
        self.assertNotIn("stale-source:old", json.dumps(candidate_profiles_payload))
        self.assertNotIn("stale-source:old", json.dumps(llm_payload))


if __name__ == "__main__":
    unittest.main()
