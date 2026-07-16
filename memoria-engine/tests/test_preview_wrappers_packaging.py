from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


PREVIEW_WRAPPER_CONTRACTS = {
    "build_verified_facts_preview.ps1": {
        "module": "caduti_fonti_report.document_analysis.verified_facts_preview",
        "tokens": [
            "[string]$EvidenceDatabasePath",
            "--evidence-source-run-id",
        ],
    },
    "build_verified_facts_profile_patch_preview.ps1": {
        "module": "caduti_fonti_report.document_analysis.verified_facts_profile_patch_preview",
        "tokens": [
            "[string]$VerifiedFactsPreviewJson",
            "--verified-facts-preview-json",
        ],
    },
    "build_dataset_export_preview.ps1": {
        "module": "caduti_fonti_report.document_analysis.dataset_export_preview",
        "tokens": [
            "[string]$EvidenceDatabasePath",
            "[string[]]$EvidenceSourceRunId",
            "[string]$VerifiedFactsPreviewJson",
            "[string]$ProfilePatchPreviewJson",
            "--evidence-source-run-id",
            "--profile-patch-preview-json",
        ],
    },
    "build_publication_card_snapshot_preview.ps1": {
        "module": "caduti_fonti_report.document_analysis.publication_card_snapshot_preview",
        "tokens": [
            "[string]$ModelCardsManifestJson",
            "[string]$DatasetExportPreviewJson",
            "[string[]]$ProfileId",
            "--model-cards-manifest-json",
            "--dataset-export-preview-json",
        ],
    },
    "build_review_decision_conflict_register_preview.ps1": {
        "module": "caduti_fonti_report.document_analysis.review_decision_conflict_register_preview",
        "tokens": [
            "[string]$EvidenceDatabasePath",
            "[string[]]$EvidenceSourceRunId",
            "[string[]]$ProfileId",
            "--evidence-source-run-id",
        ],
    },
    "build_review_store_preview.ps1": {
        "module": "caduti_fonti_report.document_analysis.review_store_preview",
        "tokens": [
            "[string]$ReviewRegisterJson",
            "[string]$EvidenceDatabasePath",
            "[string[]]$EvidenceSourceRunId",
            "[string[]]$ProfileId",
            "--review-register-json",
        ],
    },
    "promote_profile_patch_preview.ps1": {
        "module": "caduti_fonti_report.promote_profile_patch_preview",
        "tokens": [
            "[string]$ProfilePatchPreviewJson",
            "[switch]$Apply",
            "--profile-patch-preview-json",
        ],
    },
}


class PreviewWrapperPackagingTests(unittest.TestCase):
    def test_preview_wrappers_exist_and_invoke_expected_modules(self) -> None:
        for script_name, contract in PREVIEW_WRAPPER_CONTRACTS.items():
            with self.subTest(script=script_name):
                script = ROOT_DIR / "scripts" / script_name

                self.assertTrue(script.exists())
                self.assertIn(contract["module"], script.read_text(encoding="utf-8"))

    def test_preview_wrappers_expose_public_parameters(self) -> None:
        for script_name, contract in PREVIEW_WRAPPER_CONTRACTS.items():
            with self.subTest(script=script_name):
                text = (ROOT_DIR / "scripts" / script_name).read_text(encoding="utf-8")

                for token in contract["tokens"]:
                    self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
