from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_distribution_archive_excludes_legacy_operational_data(self) -> None:
        attributes = (ROOT_DIR.parent / ".gitattributes").read_text(encoding="utf-8")

        self.assertIn("memoria-engine/ricerche/person_profiles/** export-ignore", attributes)
        self.assertIn("memoria-engine/ricerche/caduti_purocielo.csv export-ignore", attributes)
        self.assertIn("memoria-engine/ricerche/mvp/** export-ignore", attributes)

    def test_pyproject_declares_library_package_with_minimal_memoria_cli(self) -> None:
        pyproject = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["name"], "caduti-fonti-report")
        self.assertIn("PyYAML>=6.0", pyproject["project"]["dependencies"])
        self.assertEqual(pyproject["project"]["scripts"]["memoria"], "caduti_fonti_report.memoria_cli:main")
        self.assertEqual(pyproject["tool"]["setuptools"]["packages"]["find"]["where"], ["code"])

    def test_package_main_is_importable_from_code_directory(self) -> None:
        sys.path.insert(0, str(ROOT_DIR / "code"))
        try:
            from caduti_fonti_report import main
        finally:
            sys.path.pop(0)

        self.assertTrue(callable(main))

    def test_run_tests_script_exists(self) -> None:
        script = ROOT_DIR / "scripts" / "run_tests.ps1"

        self.assertTrue(script.exists())
        self.assertIn("unittest discover -s tests -v", script.read_text(encoding="utf-8"))

    def test_export_person_queries_script_exists(self) -> None:
        script = ROOT_DIR / "scripts" / "export_person_queries.ps1"

        self.assertTrue(script.exists())
        text = script.read_text(encoding="utf-8")
        self.assertIn("caduti_fonti_report.export_person_queries", text)
        self.assertIn("ValueFromRemainingArguments", text)

    def test_create_raw_reference_script_exists(self) -> None:
        script = ROOT_DIR / "scripts" / "create_raw_reference.ps1"

        self.assertTrue(script.exists())
        text = script.read_text(encoding="utf-8")
        self.assertIn("caduti_fonti_report.create_raw_reference", text)
        self.assertIn("ValueFromRemainingArguments", text)

    def test_export_person_profiles_does_not_default_to_legacy_csv(self) -> None:
        script = ROOT_DIR / "scripts" / "export_person_profiles.ps1"
        text = script.read_text(encoding="utf-8")

        self.assertIn("[Parameter(Mandatory = $true)]", text)
        self.assertIn("[string]$Csv", text)
        self.assertIn("[string]$OutputDir", text)
        self.assertIn("[switch]$AllowLegacyCsv", text)
        self.assertNotIn('[string]$Csv = "ricerche\\caduti_purocielo.csv"', text)
        self.assertNotIn('[string]$OutputDir = "ricerche\\person_profiles"', text)

    def test_profile_scripts_require_explicit_profiles_index(self) -> None:
        script_names = [
            "analyze_source_documents.ps1",
            "build_feedback_search_plan.ps1",
            "build_mvp_pilot_summary.ps1",
            "plan_profile_search.ps1",
            "run_profiles_meta_search.ps1",
        ]
        for script_name in script_names:
            with self.subTest(script_name=script_name):
                text = (ROOT_DIR / "scripts" / script_name).read_text(encoding="utf-8")
                self.assertIn("[string]$ProfilesIndex", text)
                self.assertIn("[Parameter(Mandatory = $true)]", text)
                self.assertNotIn('[string]$ProfilesIndex = "ricerche\\person_profiles\\purocielo.index.jsonld"', text)

    def test_python_clis_do_not_default_to_legacy_profile_or_csv_inputs(self) -> None:
        checked_modules = [
            ROOT_DIR / "code" / "caduti_fonti_report" / "runner.py",
            ROOT_DIR / "code" / "caduti_fonti_report" / "orchestrator.py",
            ROOT_DIR / "code" / "caduti_fonti_report" / "live_source_review.py",
            ROOT_DIR / "code" / "caduti_fonti_report" / "evidence_connector_review.py",
            ROOT_DIR / "code" / "caduti_fonti_report" / "export_person_queries.py",
            ROOT_DIR / "code" / "caduti_fonti_report" / "profiles_runner.py",
            ROOT_DIR / "code" / "caduti_fonti_report" / "search_strategy_planner.py",
            ROOT_DIR / "code" / "caduti_fonti_report" / "document_analysis" / "feedback_search_plan.py",
            ROOT_DIR / "code" / "caduti_fonti_report" / "document_analysis" / "person_linking.py",
        ]
        for module_path in checked_modules:
            with self.subTest(module=module_path.name):
                text = module_path.read_text(encoding="utf-8")
                self.assertNotIn('default="ricerche/caduti_purocielo.csv"', text)
                self.assertNotIn('default="ricerche/person_profiles/purocielo.index.jsonld"', text)

    def test_legacy_memoria_wrapper_does_not_fallback_to_repo_person_profiles(self) -> None:
        text = (ROOT_DIR / "scripts" / "memoria.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $resolvedRoot "ricerche\\person_profiles\\purocielo.index.jsonld"', text)
        self.assertNotIn('Join-Path $repoRoot "ricerche\\person_profiles\\purocielo.index.jsonld"', text)

    def test_sqlite_store_scripts_exist(self) -> None:
        init_script = ROOT_DIR / "scripts" / "init_evidence_db.ps1"
        import_script = ROOT_DIR / "scripts" / "import_person_queries_to_db.ps1"
        report_import_script = ROOT_DIR / "scripts" / "import_report_to_db.ps1"
        document_evidence_import_script = ROOT_DIR / "scripts" / "import_document_analysis_evidence_to_db.ps1"
        meta_search_script = ROOT_DIR / "scripts" / "run_meta_search.ps1"
        inspect_script = ROOT_DIR / "scripts" / "inspect_evidence_db.ps1"
        audit_script = ROOT_DIR / "scripts" / "export_audit_report.ps1"
        audit_csv_script = ROOT_DIR / "scripts" / "export_audit_csv.ps1"
        obsidian_script = ROOT_DIR / "scripts" / "export_obsidian_vault.ps1"
        extract_table_claims_script = ROOT_DIR / "scripts" / "extract_table_claims.ps1"
        validate_sources_script = ROOT_DIR / "scripts" / "validate_sources_registry.ps1"
        workspace_pipeline_script = ROOT_DIR / "scripts" / "run_mvp_workspace_pipeline.ps1"
        mvp_review_queue_script = ROOT_DIR / "scripts" / "build_mvp_review_queue.ps1"
        mvp_review_decisions_script = ROOT_DIR / "scripts" / "summarize_mvp_review_decisions.ps1"
        mvp_package_readiness_script = ROOT_DIR / "scripts" / "build_mvp_package_readiness.ps1"
        mvp_funding_dossier_script = ROOT_DIR / "scripts" / "build_mvp_funding_dossier.ps1"
        mvp_funding_package_script = ROOT_DIR / "scripts" / "build_mvp_funding_package.ps1"
        mvp_pilot_cards_digest_script = ROOT_DIR / "scripts" / "build_mvp_pilot_cards_digest.ps1"
        mvp_model_cards_script = ROOT_DIR / "scripts" / "build_mvp_model_cards.ps1"
        mvp_consolidated_ledger_script = ROOT_DIR / "scripts" / "build_mvp_consolidated_review_ledger.ps1"
        mvp_review_session_script = ROOT_DIR / "scripts" / "build_mvp_review_session.ps1"
        mvp_review_dashboard_script = ROOT_DIR / "scripts" / "build_mvp_review_dashboard.ps1"
        mvp_review_focus_table_script = ROOT_DIR / "scripts" / "build_mvp_review_focus_decisions_table.ps1"
        mvp_historical_targets_script = ROOT_DIR / "scripts" / "build_mvp_historical_review_targets.ps1"
        evidence_store_profile_status_script = ROOT_DIR / "scripts" / "build_evidence_store_profile_status.ps1"
        mvp_document_intake_script = ROOT_DIR / "scripts" / "check_mvp_document_intake.ps1"
        image_preprocessing_plan_script = ROOT_DIR / "scripts" / "build_image_preprocessing_plan.ps1"
        feedback_triage_table_script = ROOT_DIR / "scripts" / "build_research_feedback_actions_review_table.ps1"
        feedback_triage_summary_script = ROOT_DIR / "scripts" / "summarize_research_feedback_actions_review_table.ps1"
        source_coverage_script = ROOT_DIR / "scripts" / "summarize_source_coverage.ps1"
        profiles_meta_search_script = ROOT_DIR / "scripts" / "run_profiles_meta_search.ps1"

        self.assertTrue(init_script.exists())
        self.assertTrue(import_script.exists())
        self.assertTrue(report_import_script.exists())
        self.assertTrue(document_evidence_import_script.exists())
        self.assertTrue(meta_search_script.exists())
        self.assertTrue(inspect_script.exists())
        self.assertTrue(audit_script.exists())
        self.assertTrue(audit_csv_script.exists())
        self.assertTrue(obsidian_script.exists())
        self.assertTrue(extract_table_claims_script.exists())
        self.assertTrue(validate_sources_script.exists())
        self.assertTrue(workspace_pipeline_script.exists())
        self.assertTrue(mvp_review_queue_script.exists())
        self.assertTrue(mvp_review_decisions_script.exists())
        self.assertTrue(mvp_package_readiness_script.exists())
        self.assertTrue(mvp_funding_dossier_script.exists())
        self.assertTrue(mvp_funding_package_script.exists())
        self.assertTrue(mvp_pilot_cards_digest_script.exists())
        self.assertTrue(mvp_model_cards_script.exists())
        self.assertTrue(mvp_consolidated_ledger_script.exists())
        self.assertTrue(mvp_review_session_script.exists())
        self.assertTrue(mvp_review_dashboard_script.exists())
        self.assertTrue(mvp_review_focus_table_script.exists())
        self.assertTrue(mvp_historical_targets_script.exists())
        self.assertTrue(evidence_store_profile_status_script.exists())
        self.assertTrue(mvp_document_intake_script.exists())
        self.assertTrue(image_preprocessing_plan_script.exists())
        self.assertTrue(feedback_triage_table_script.exists())
        self.assertTrue(feedback_triage_summary_script.exists())
        self.assertTrue(source_coverage_script.exists())
        self.assertTrue(profiles_meta_search_script.exists())
        self.assertIn("caduti_fonti_report.init_evidence_db", init_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.import_person_queries_to_db",
            import_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.import_report_to_db",
            report_import_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.document_analysis.evidence_store_import",
            document_evidence_import_script.read_text(encoding="utf-8"),
        )
        self.assertIn("caduti_fonti_report.orchestrator", meta_search_script.read_text(encoding="utf-8"))
        self.assertIn("caduti_fonti_report.inspect_evidence_db", inspect_script.read_text(encoding="utf-8"))
        self.assertIn("caduti_fonti_report.export_audit_report", audit_script.read_text(encoding="utf-8"))
        self.assertIn("caduti_fonti_report.export_audit_csv", audit_csv_script.read_text(encoding="utf-8"))
        self.assertIn("caduti_fonti_report.export_obsidian_vault", obsidian_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.extract_table_claims",
            extract_table_claims_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.validate_sources_registry",
            validate_sources_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_review_queue",
            mvp_review_queue_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_review_decisions",
            mvp_review_decisions_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_package_readiness",
            mvp_package_readiness_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_funding_dossier",
            mvp_funding_dossier_script.read_text(encoding="utf-8"),
        )
        self.assertIn("[string]$VerifiedFactsPreviewJson", mvp_funding_dossier_script.read_text(encoding="utf-8"))
        self.assertIn("--verified-facts-preview-json", mvp_funding_dossier_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_funding_package",
            mvp_funding_package_script.read_text(encoding="utf-8"),
        )
        self.assertIn("[string]$QualityGateStatus", mvp_funding_package_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_pilot_cards_digest",
            mvp_pilot_cards_digest_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_model_cards",
            mvp_model_cards_script.read_text(encoding="utf-8"),
        )
        self.assertIn("[string]$VerifiedFactsPreviewJson", mvp_model_cards_script.read_text(encoding="utf-8"))
        self.assertIn("--verified-facts-preview-json", mvp_model_cards_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_consolidated_review_ledger",
            mvp_consolidated_ledger_script.read_text(encoding="utf-8"),
        )
        self.assertIn("[string]$EvidenceDatabasePath", mvp_consolidated_ledger_script.read_text(encoding="utf-8"))
        self.assertIn("--evidence-db", mvp_consolidated_ledger_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_review_session",
            mvp_review_session_script.read_text(encoding="utf-8"),
        )
        self.assertIn("[string]$ConsolidatedLedgerJson", mvp_review_session_script.read_text(encoding="utf-8"))
        self.assertIn("--consolidated-ledger-json", mvp_review_session_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_review_dashboard",
            mvp_review_dashboard_script.read_text(encoding="utf-8"),
        )
        self.assertIn("[string]$ReviewSessionJson", mvp_review_dashboard_script.read_text(encoding="utf-8"))
        self.assertIn("--review-session-json", mvp_review_dashboard_script.read_text(encoding="utf-8"))
        self.assertIn("[string]$VerifiedFactsPreviewJson", mvp_review_dashboard_script.read_text(encoding="utf-8"))
        self.assertIn("--verified-facts-preview-json", mvp_review_dashboard_script.read_text(encoding="utf-8"))
        self.assertIn("[string]$ProfilePatchPreviewJson", mvp_review_dashboard_script.read_text(encoding="utf-8"))
        self.assertIn("--profile-patch-preview-json", mvp_review_dashboard_script.read_text(encoding="utf-8"))
        self.assertIn("[string]$ProfilePatchSandboxDir", mvp_review_dashboard_script.read_text(encoding="utf-8"))
        self.assertIn("--profile-patch-sandbox-dir", mvp_review_dashboard_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_review_focus_table",
            mvp_review_focus_table_script.read_text(encoding="utf-8"),
        )
        self.assertIn("BuildTable", mvp_review_focus_table_script.read_text(encoding="utf-8"))
        self.assertIn("ConvertTable", mvp_review_focus_table_script.read_text(encoding="utf-8"))
        self.assertIn("BuildQueueCards", mvp_review_focus_table_script.read_text(encoding="utf-8"))
        self.assertIn("[string]$ReviewQueueJson", mvp_review_focus_table_script.read_text(encoding="utf-8"))
        self.assertIn("[string[]]$ItemId", mvp_review_focus_table_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_historical_review_targets",
            mvp_historical_targets_script.read_text(encoding="utf-8"),
        )
        self.assertIn("--review-queue-json", mvp_historical_targets_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.evidence_store_profile_status",
            evidence_store_profile_status_script.read_text(encoding="utf-8"),
        )
        self.assertIn("--profile-id", evidence_store_profile_status_script.read_text(encoding="utf-8"))
        self.assertIn("[string[]]$EvidenceSourceRunId", evidence_store_profile_status_script.read_text(encoding="utf-8"))
        self.assertIn("--evidence-source-run-id", evidence_store_profile_status_script.read_text(encoding="utf-8"))
        self.assertIn(
            "caduti_fonti_report.document_analysis.mvp_document_intake_preflight",
            mvp_document_intake_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.document_analysis.research_feedback_triage",
            feedback_triage_table_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.document_analysis.research_feedback_triage",
            feedback_triage_summary_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "caduti_fonti_report.source_coverage_summary",
            source_coverage_script.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "--acquire-documents-root",
            profiles_meta_search_script.read_text(encoding="utf-8"),
        )
        document_pipeline_text = (ROOT_DIR / "scripts" / "run_document_research_pipeline.ps1").read_text(encoding="utf-8")
        self.assertIn("[string]$AcquireDocumentsRoot", document_pipeline_text)
        self.assertIn("--acquire-documents-root", document_pipeline_text)

    def test_mvp_workspace_pipeline_uses_canonical_shared_paths(self) -> None:
        script = ROOT_DIR / "scripts" / "run_mvp_workspace_pipeline.ps1"
        text = script.read_text(encoding="utf-8")

        self.assertIn("[string]$WorkspaceRoot", text)
        self.assertIn("[string]$InputRootDir", text)
        self.assertIn("[switch]$ReportsOnly", text)
        self.assertIn("[switch]$SkipEvidenceImport", text)
        self.assertIn('[ValidateSet("Demo", "Full", "Debug")]', text)
        self.assertIn('[string]$OutputProfile = "Full"', text)
        self.assertIn("[string]$ReuseLocalRunId", text)
        self.assertIn("[string]$ReusePipelineRunId", text)
        self.assertIn("documenti_da_processare", text)
        self.assertIn("$defaultRawDir", text)
        self.assertIn("Resolve-Path -LiteralPath $InputRootDir", text)
        self.assertIn("$effectiveProcessedDir", text)
        self.assertIn('Join-Path $localRunDir "processed_documents"', text)
        self.assertIn("documenti_processati", text)
        self.assertIn("database", text)
        self.assertIn("run_local_document_processing.ps1", text)
        self.assertIn("run_document_research_pipeline.ps1", text)
        self.assertIn("export_obsidian_vault.ps1", text)
        self.assertIn("ResultsDir = $resultsDir", text)
        self.assertIn("ResearchDir = $researchDir", text)
        self.assertIn("[switch]$RunOcr", text)
        self.assertIn("RunOcr", text)
        self.assertIn("PreprocessBeforeOcr", text)
        self.assertIn("EnableRegionOcr", text)
        self.assertIn("OcrLanguage", text)
        self.assertIn("[int]$OcrProgressEvery", text)
        self.assertIn('localArgs["OcrProgressEvery"] = $OcrProgressEvery', text)
        self.assertIn("[string]$ProfilesIndex", text)
        self.assertIn("[string]$ReviewDecisionsJson", text)
        self.assertIn("[string]$Source", text)
        self.assertIn("[switch]$IncludeSearchPlan", text)
        self.assertIn("[switch]$ExecuteFirstPlannedAttempt", text)
        self.assertIn("[switch]$AcquireOnlineDocuments", text)
        self.assertIn("[string]$AcquireDocumentsRoot", text)
        self.assertIn("$resolvedAcquireDocumentsRoot", text)
        self.assertIn("fonti_online", text)
        self.assertIn("[switch]$BuildCandidateProfileReview", text)
        self.assertIn("[string[]]$AcceptedCandidateProfileId", text)
        self.assertIn("[int]$CandidateProfileLimit = 10", text)
        self.assertIn("$defaultProfilesIndex", text)
        self.assertIn("$resolvedProfilesIndex", text)
        self.assertIn("$candidateProfilesJson", text)
        self.assertIn("$candidateProfileReviewDir", text)
        self.assertIn("$previewProfilesIndex", text)
        self.assertIn("$resolvedReviewDecisionsJson", text)
        self.assertIn("Indice profili: $resolvedProfilesIndex", text)
        self.assertIn("Indice profili preview attivo", text)
        self.assertIn("Profilo pilota preview auto", text)
        self.assertIn("Decisioni review: $resolvedReviewDecisionsJson", text)
        self.assertIn("$reviewDecisionsInput = [ordered]@", text)
        self.assertIn("review_decisions_input = $reviewDecisionsInput", text)
        self.assertIn("generated_template", text)
        self.assertIn("external_compiled_file", text)
        self.assertIn("## Decisioni review usate", text)
        self.assertIn("[string[]]$ProfileId", text)
        self.assertIn('Profili pilota', text)
        self.assertIn("build_candidate_person_profile_review.ps1", text)
        self.assertIn('candidateReviewArgs["AcceptedCandidateProfileId"]', text)
        self.assertIn("reason=explicit_profiles_index", text)
        self.assertIn("LocalRunDir", text)
        self.assertIn("ProfilesIndex = $resolvedProfilesIndex", text)
        self.assertIn("-DecisionsJson $resolvedReviewDecisionsJson", text)
        self.assertIn("$normalizedProfileId = @(Normalize-StringArray -Values $ProfileId)", text)
        self.assertIn('$summaryArgs["ProfileId"] = $normalizedProfileId', text)
        self.assertIn("build_mvp_review_queue.ps1", text)
        self.assertIn("summarize_mvp_review_decisions.ps1", text)
        self.assertIn("build_research_feedback_actions_review_table.ps1", text)
        self.assertIn("summarize_research_feedback_actions_review_table.ps1", text)
        self.assertIn("summarize_source_coverage.ps1", text)
        self.assertIn("profiles_meta_search.json", text)
        self.assertIn("source_coverage_summary.md", text)
        self.assertIn('pipelineArgs["Source"] = $Source', text)
        self.assertIn('pipelineArgs["IncludeSearchPlan"] = $true', text)
        self.assertIn('pipelineArgs["ExecuteFirstPlannedAttempt"] = $true', text)
        self.assertIn('pipelineArgs["AcquireDocumentsRoot"] = $resolvedAcquireDocumentsRoot', text)
        self.assertIn("Documenti online acquisiti", text)
        self.assertIn("build_mvp_package_readiness.ps1", text)
        self.assertIn("build_mvp_consolidated_review_ledger.ps1", text)
        self.assertIn('ledgerArgs["EvidenceDatabasePath"] = $dbPath', text)
        self.assertIn('ledgerArgs["EvidenceSourceRunId"] = $pipelineRunId', text)
        self.assertIn("STEP SKIP import_document_analysis_evidence_to_db reason=skip_evidence_import", text)
        self.assertIn("STEP SKIP build_verified_facts_preview reason=skip_evidence_import", text)
        self.assertIn("verified_facts.preview.json", text)
        self.assertIn("verified_facts.preview.md", text)
        self.assertIn("build_verified_facts_preview.ps1", text)
        self.assertIn("STEP SKIP build_verified_facts_profile_patch_preview reason=skip_evidence_import", text)
        self.assertIn("STEP SKIP build_review_decision_conflict_register_preview reason=skip_evidence_import", text)
        self.assertIn("STEP SKIP build_dataset_export_preview reason=skip_evidence_import", text)
        self.assertIn("STEP SKIP build_publication_card_snapshot_preview reason=skip_evidence_import", text)
        self.assertIn("profile_patch.preview.json", text)
        self.assertIn("profile_patch.preview.md", text)
        self.assertIn("review_decision_conflict_register.preview.json", text)
        self.assertIn("review_decision_conflict_register.preview.md", text)
        self.assertIn("dataset_export.preview.json", text)
        self.assertIn("dataset_export.preview.md", text)
        self.assertIn("publication_card_snapshots_preview", text)
        self.assertIn("build_verified_facts_profile_patch_preview.ps1", text)
        self.assertIn("build_review_decision_conflict_register_preview.ps1", text)
        self.assertIn("build_dataset_export_preview.ps1", text)
        self.assertIn("build_publication_card_snapshot_preview.ps1", text)
        self.assertIn("-VerifiedFactsPreviewJson $verifiedFactsPreviewJson", text)
        self.assertIn("not_publishable_without_editorial_review", text)
        self.assertIn("verifiedFactsPreviewArgs", text)
        self.assertIn('verifiedFactsPreviewArgs["ProfileId"] = $normalizedProfileId', text)
        self.assertIn('profilePatchPreviewArgs["ProfileId"] = $normalizedProfileId', text)
        self.assertIn('decisionConflictRegisterPreviewArgs["ProfileId"] = $normalizedProfileId', text)
        self.assertIn('datasetExportPreviewArgs["ProfileId"] = $normalizedProfileId', text)
        self.assertIn('snapshotPreviewArgs["ProfileId"] = $normalizedProfileId', text)
        self.assertIn("VerifiedFactsPreviewJson = $verifiedFactsPreviewJson", text)
        self.assertIn("ProfilePatchPreviewJson = $profilePatchPreviewJson", text)
        self.assertIn("DatasetExportPreviewJson = $datasetExportPreviewJson", text)
        self.assertIn("OutputJson = $reviewDecisionConflictRegisterPreviewJson", text)
        self.assertIn("OutputMd = $reviewDecisionConflictRegisterPreviewMd", text)
        self.assertIn("EvidenceDatabasePath = $dbPath", text)
        self.assertIn("EvidenceSourceRunId = $pipelineRunId", text)
        self.assertIn('if (-not $SkipEvidenceImport)', text)
        self.assertIn('skip_evidence_import = [bool]$SkipEvidenceImport', text)
        self.assertIn("mvp_consolidated_review_ledger.md", text)
        self.assertIn("Consolidated Review Ledger MVP", text)
        self.assertIn("build_mvp_pilot_cards_digest.ps1", text)
        self.assertIn("mvp_pilot_cards_digest.md", text)
        self.assertIn("Digest schede pilota MVP", text)
        self.assertIn('$modelCardsDir = Join-Path $pipelineRunDir "schede_modello"', text)
        self.assertIn('$fundingExcerptsDir = Join-Path $pipelineRunDir "funding_excerpts"', text)
        self.assertIn("build_mvp_model_cards.ps1", text)
        self.assertIn("-DigestJson $pilotCardsDigestJson", text)
        self.assertIn("-ReviewSessionJson $reviewSessionJson", text)
        self.assertIn("-VerifiedFactsPreviewJson $verifiedFactsPreviewJson", text)
        self.assertIn("-OutputDir $modelCardsDir", text)
        self.assertIn("-FundingExcerptsDir $fundingExcerptsDir", text)
        self.assertIn("schede_modello", text)
        self.assertIn("funding_excerpts", text)
        self.assertIn("Indice schede modello MVP", text)
        self.assertIn("Manifest schede modello MVP", text)
        self.assertIn("Estratti finanziatore da schede modello", text)
        self.assertIn("Schede modello MVP: $modelCardsDir", text)
        self.assertIn("Estratti finanziatore MVP: $fundingExcerptsDir", text)
        self.assertIn("build_mvp_review_session.ps1", text)
        self.assertIn("-ConsolidatedLedgerJson $consolidatedLedgerJson", text)
        self.assertIn("review_session.md", text)
        self.assertIn("Sessione revisione MVP", text)
        self.assertIn("build_mvp_historical_review_targets.ps1", text)
        self.assertIn("historical_review_targets.md", text)
        self.assertIn("Target storici revisionabili", text)
        self.assertIn("Verified facts preview", text)
        self.assertIn("Verified facts preview MVP: $verifiedFactsPreviewMd", text)
        self.assertIn("ProfilePatch preview", text)
        self.assertIn("ProfilePatch preview MVP: $profilePatchPreviewMd", text)
        self.assertIn("ReviewDecision/Conflict register preview", text)
        self.assertIn("ReviewDecision/Conflict register preview MVP: $reviewDecisionConflictRegisterPreviewMd", text)
        self.assertIn("Dataset export preview", text)
        self.assertIn("Dataset export preview MVP: $datasetExportPreviewMd", text)
        self.assertIn("PublicationCardSnapshot preview", text)
        self.assertIn("PublicationCardSnapshot preview MVP: $publicationCardSnapshotsDir", text)
        self.assertIn("profile_patch_preview", text)
        self.assertIn("review_decision_conflict_register_preview", text)
        self.assertIn("review_decision_conflict_register_preview_json", text)
        self.assertIn("dataset_export_preview", text)
        self.assertIn("publication_card_snapshot_index", text)
        self.assertIn("publication_card_snapshot_manifest", text)
        self.assertIn("build_mvp_review_focus_decisions_table.ps1", text)
        self.assertIn("review_focus_decisions_table.md", text)
        self.assertIn("Tabella decisioni focus review", text)
        self.assertIn("build_mvp_funding_dossier.ps1", text)
        self.assertIn("-SourceCoverageSummaryJson $sourceCoverageJson", text)
        self.assertIn("mvp_funding_dossier.md", text)
        self.assertIn("import_document_analysis_evidence_to_db.ps1", text)
        self.assertIn("evidence_store_import.md", text)
        self.assertIn("Import evidence store generale", text)
        self.assertIn("evidence_database = $dbPath", text)
        self.assertIn("inspect_evidence_db.ps1", text)
        self.assertIn("-EvidenceImports", text)
        self.assertIn("-EvidenceRecords", text)
        self.assertIn("-EvidenceSubjects", text)
        self.assertIn("-EvidenceCoverage", text)
        self.assertIn("mvp_run_index.md", text)
        self.assertIn("mvp_run_index.json", text)
        self.assertIn("quicklook_commands", text)
        self.assertIn("artifact_groups", text)
        self.assertIn("output_profile = $OutputProfile", text)
        self.assertIn("output_profile_guidance = $outputProfileGuidance", text)
        self.assertIn("hidden_by_profile = $hiddenByProfile", text)
        self.assertIn("recommended_reading_order = $recommendedReadingOrder", text)
        self.assertIn("Get-MvpRecommendedReadingOrder", text)
        self.assertIn("Get-MvpOutputProfileGuidance", text)
        self.assertIn("primary_human_output", text)
        self.assertIn("historian_review", text)
        self.assertIn("machine_audit", text)
        self.assertIn("technical_diagnostics", text)
        self.assertIn("Mappa output", text)
        self.assertIn("Profilo output", text)
        self.assertIn("Percorso Demo", text)
        self.assertIn("Aprire questi file nell'ordine indicato", text)
        self.assertIn("Non aprire di default in questo profilo", text)
        self.assertIn("Comandi rapidi PowerShell", text)
        self.assertIn('Get-Content "$run\\historian_review\\review_decision_conflict_register.preview.md"', text)
        self.assertIn('Get-Content "$run\\dataset_export.preview.md"', text)
        self.assertIn('Get-Content "$run\\publication_card_snapshots_preview\\README.md"', text)
        self.assertNotIn("mvp_model_cards_reviewed", text)
        self.assertIn("reports_only = [bool]$ReportsOnly", text)
        self.assertIn("input_root_dir = $rawDir", text)
        self.assertIn("input_root_is_subset = $inputRootIsSubset", text)
        self.assertIn("processed_dir = $effectiveProcessedDir", text)
        self.assertIn("STEP SKIP run_local_document_processing reason=reports_only", text)
        self.assertIn("STEP SKIP run_document_research_pipeline reason=reports_only", text)
        self.assertIn("Write-MvpRunIndex", text)
        self.assertIn("Indice run MVP", text)
        self.assertIn('"mvp_pilot_summary"', text)
        self.assertIn("--mvp-review-queue", text)
        self.assertIn("--mvp-review-decisions-summary", text)
        self.assertIn("Package readiness MVP", text)
        self.assertIn("Dossier finanziamento MVP", text)
        self.assertIn("Source coverage summary", text)
        self.assertNotIn('"-RootDir", $resolvedWorkspaceRoot', text)

    def test_quality_gate_wrapper_can_write_optional_mvp_baseline(self) -> None:
        script = ROOT_DIR / "scripts" / "run_quality_gate.ps1"
        quality_gate_tests = ROOT_DIR / "scripts" / "test_quality_gate.ps1"
        text = script.read_text(encoding="utf-8")

        self.assertIn("[string]$BaselineOutputDir", text)
        self.assertIn("[string]$BaselineRunId", text)
        self.assertIn("caduti_fonti_report.document_analysis.quality_gate_baseline", text)
        self.assertIn("--status passed", text)
        self.assertIn("tests/test_quality_gate_baseline.py", quality_gate_tests.read_text(encoding="utf-8"))

    def test_mvp_funding_dossier_wrapper_accepts_source_coverage_summary(self) -> None:
        script = ROOT_DIR / "scripts" / "build_mvp_funding_dossier.ps1"
        text = script.read_text(encoding="utf-8")

        self.assertIn("[string]$SourceCoverageSummaryJson", text)
        self.assertIn("--source-coverage-summary-json", text)
        self.assertIn("Test-Path -LiteralPath $SourceCoverageSummaryJson", text)

    def test_local_document_processing_wrapper_exposes_ocr_progress_every(self) -> None:
        script = ROOT_DIR / "scripts" / "run_local_document_processing.ps1"
        text = script.read_text(encoding="utf-8")

        self.assertIn("[int]$OcrProgressEvery = 25", text)
        self.assertIn("--ocr-progress-every", text)

    def test_candidate_person_profile_review_wrapper_accepts_inline_ids(self) -> None:
        script = ROOT_DIR / "scripts" / "build_candidate_person_profile_review.ps1"
        text = script.read_text(encoding="utf-8")

        self.assertIn("[string[]]$AcceptedCandidateProfileId", text)
        self.assertIn("--accepted-candidate-profile-id", text)
        self.assertIn("foreach ($candidateProfileId in $AcceptedCandidateProfileId)", text)

    def test_sqlite_wrappers_accept_explicit_database_path_parameter(self) -> None:
        init_script = (ROOT_DIR / "scripts" / "init_evidence_db.ps1").read_text(encoding="utf-8")
        inspect_script = (ROOT_DIR / "scripts" / "inspect_evidence_db.ps1").read_text(encoding="utf-8")

        self.assertIn("[string]$DatabasePath", init_script)
        self.assertIn("@(\"--db\", $DatabasePath)", init_script)
        self.assertIn("[string]$DatabasePath", inspect_script)
        self.assertIn("[switch]$Summary", inspect_script)
        self.assertIn("[switch]$EvidenceImports", inspect_script)
        self.assertIn("[switch]$EvidenceRecords", inspect_script)
        self.assertIn("[switch]$EvidenceSubjects", inspect_script)
        self.assertIn("[switch]$EvidenceCoverage", inspect_script)
        self.assertIn("@(\"--db\", $DatabasePath)", inspect_script)
        self.assertIn("--evidence-imports", inspect_script)
        self.assertIn("--evidence-records", inspect_script)
        self.assertIn("--evidence-subjects", inspect_script)
        self.assertIn("--evidence-coverage", inspect_script)

    def test_powershell_script_conventions_are_documented(self) -> None:
        doc = ROOT_DIR / "docs" / "convenzioni-script-powershell.md"
        session_contract = ROOT_DIR / "docs" / "playbooks" / "codex-session-contract.md"
        task_router = ROOT_DIR / "docs" / "playbooks" / "codex-task-router.md"
        quality_gate = ROOT_DIR / "docs" / "playbooks" / "codex-quality-gate-core.md"
        playbook_readme = ROOT_DIR / "docs" / "playbooks" / "README.md"

        self.assertTrue(doc.exists())
        text = doc.read_text(encoding="utf-8")
        self.assertIn("Non creare", text)
        self.assertIn("[project.scripts]", text)
        self.assertIn("windows sandbox: spawn setup refresh", text)
        self.assertIn(".\\tools\\pwsh\\pwsh.exe", text)
        self.assertIn("-NoLogo -NoProfile -ExecutionPolicy Bypass -File", text)
        self.assertIn("Get-Content -Path .\\file.py -TotalCount 40", text)
        self.assertIn("parallelizzare con `multi_tool_use.parallel` solo comandi senza pipeline shell", text)
        self.assertIn('-ProfileId "person:purocielo:andreoli-dino","person:purocielo:guazzaloca-laura"', text)
        self.assertIn(".\\scripts\\memoria.ps1", session_contract.read_text(encoding="utf-8"))
        self.assertIn("Guide consolidate", session_contract.read_text(encoding="utf-8"))
        self.assertIn("documentation touchpoint", task_router.read_text(encoding="utf-8"))
        self.assertIn("test mirati", quality_gate.read_text(encoding="utf-8"))
        self.assertIn("codex-session-contract.md", playbook_readme.read_text(encoding="utf-8"))

    def test_mvp_workspace_profile_id_examples_use_powershell_array_syntax(self) -> None:
        guide = (ROOT_DIR / "docs" / "guida-comandi-processazione-locale-online.md").read_text(encoding="utf-8")
        status = (ROOT_DIR / "docs" / "stato-implementazione-meta-motore.md").read_text(encoding="utf-8")

        self.assertIn('-ProfileId "person:purocielo:andreoli-dino","person:purocielo:balboni-william","person:purocielo:bendini-ateo"', guide)
        self.assertIn("[string[]]$ProfileId", status)
        self.assertIn("`-ProfileId` ripetuto piu' volte", guide)


if __name__ == "__main__":
    unittest.main()
