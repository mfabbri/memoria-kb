from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from caduti_fonti_report.document_analysis.document_transcription_review import (  # noqa: E402
    run_document_transcription_wizard,
)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aPioAAAAASUVORK5CYII="
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TranscriptionWizardTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".tmp-tests"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="transcription-synthetic-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.output = self.base / "out"
        self.report = self.base / "source-report.json"
        self.ids = ["synthetic:card:image:1", "synthetic:card:image:2"]
        related = []
        self.images = []
        self.sidecars = []
        for i, document_id in enumerate(self.ids, 1):
            image = self.base / f"image-{i}.png"
            image.write_bytes(PNG)
            sidecar = self.base / f"image-{i}.png.document.yaml"
            metadata = {"document_id": document_id, "source_document_id": "synthetic:card",
                        "source_id": "synthetic", "document_class": "image_scan",
                        "media_type": "image/png", "claim_eligible": False,
                        "review_status": "unreviewed", "content_hash": digest(image)}
            sidecar.write_text(yaml.safe_dump({"document_id": document_id, "source_id": "synthetic",
                                              "file": str(image), "metadata": metadata,
                                              "url": "https://example.test/image?key=synthetic-private"}), encoding="utf-8")
            related.append({"status": "acquired", "source_document_id": document_id,
                            "parent_source_document_id": "synthetic:card", "source_id": "synthetic",
                            "file": str(image), "sidecar": str(sidecar), "content_hash": digest(image),
                            "review_status": "unreviewed", "claim_eligible": False})
            self.images.append(image)
            self.sidecars.append(sidecar)
        self.payload = {"acquired_documents_summary": {"items": [
            {"status": "acquired", "source_document_id": "synthetic:card", "source_id": "synthetic",
             "related_documents": related}]}}
        self.write_report()
        self.launcher = Path(sys.executable).parent / ("memoria.exe" if os.name == "nt" else "memoria")
        self.assertTrue(self.launcher.is_file(), "Tests require the installed memoria launcher in the project venv.")

    def write_report(self):
        self.report.write_text(json.dumps(self.payload), encoding="utf-8")

    def answers(self, *, first_text="Testo sintetico uno", first_decision="a", final="s"):
        return ["synthetic-transcriber", "Campo Alfa", "p", first_text,
                "Annotazioni", "f", "Testo sintetico due", "synthetic-reviewer",
                first_decision, "" if first_decision == "a" else "Lettura non confermata", "a", "", final]

    def command(self, document_ids=None):
        command = [str(self.launcher), "documents", "transcription-wizard", "--source-report", str(self.report),
                   "--output-dir", str(self.output)]
        for document_id in document_ids if document_ids is not None else self.ids:
            command.extend(["--document-id", document_id])
        return command

    def run_cli(self, answers=None, *, document_ids=None):
        return subprocess.run(self.command(document_ids), input="\n".join(answers or []) + "\n",
                              text=True, encoding="utf-8", capture_output=True, timeout=30, check=False,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=ROOT)

    def test_installed_launcher_success_and_hash_bound_artifacts(self):
        inputs = [self.report, *self.images, *self.sidecars]
        before = {path: digest(path) for path in inputs}
        result = self.run_cli(self.answers())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {path: digest(path) for path in inputs})
        manifest = json.loads((self.output / "transcription-manifest.json").read_text(encoding="utf-8"))
        receipt = json.loads((self.output / "transcription-review-receipt.json").read_text(encoding="utf-8"))
        self.assertTrue(receipt["review_complete"])
        self.assertFalse(receipt["reviewer_identity_authenticated"])
        self.assertEqual(receipt["manifest"]["sha256"], digest(Path(receipt["manifest"]["path"])))
        self.assertEqual(manifest["draft"]["sha256"], digest(Path(manifest["draft"]["path"])))
        self.assertEqual(manifest["source_report"]["sha256"], digest(self.report))
        for i, image in enumerate(manifest["images"]):
            self.assertEqual(image["source_document_id"], self.ids[i])
            self.assertEqual(image["parent_source_document_id"], "synthetic:card")
            self.assertEqual(image["image"]["sha256"], digest(self.images[i]))
            self.assertEqual(image["sidecar"]["sha256"], digest(self.sidecars[i]))
            self.assertEqual(image["source_review_status"], "unreviewed")
            text_ref = manifest["processed_texts"][i]
            self.assertEqual(text_ref["sha256"], digest(Path(text_ref["path"])))
            text = json.loads(Path(text_ref["path"]).read_text(encoding="utf-8"))
            self.assertEqual(text["source_document_id"], self.ids[i])
            self.assertEqual(text["transcription_method"], "manual_transcription")
            self.assertIsNone(text["confidence"])
            self.assertFalse(text["claim_eligible"])
            self.assertEqual(text["review_status"], "human_reviewed_transcription")
            self.assertEqual(text["text_sha256"], hashlib.sha256(text["text"].encode()).hexdigest())
        self.assertEqual(receipt["decisions"][0]["coverage"], "partial")
        draft = json.loads((self.output / "transcription-draft.json").read_text(encoding="utf-8"))
        self.assertTrue(all(item["review_status"] == "unreviewed" for item in draft["items"]))
        all_outputs = "".join(path.read_text(encoding="utf-8") for path in self.output.iterdir())
        for forbidden in ["synthetic-private", "CandidateEvidenceClaim", "verified_facts"]:
            self.assertNotIn(forbidden, all_outputs)
        for flag in ["canonical_write_allowed", "claim_promotion_allowed", "claim_eligible", "machine_pass"]:
            self.assertFalse(receipt[flag])

    def test_illegible_portion_remains_pending_and_has_no_invented_text(self):
        result = self.run_cli(self.answers(first_text="i", first_decision="e"))
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((self.output / "transcription-review-receipt.json").read_text())
        text = json.loads((self.output / "image-1.text.json").read_text())
        self.assertFalse(receipt["review_complete"])
        self.assertEqual(receipt["review_status"], "pending")
        self.assertEqual(text["text"], "")
        self.assertEqual(text["text_status"], "not_transcribed")
        self.assertEqual(text["review_status"], "unreviewed")

    def test_rejection_retains_draft_and_does_not_approve_text(self):
        result = self.run_cli(self.answers(first_decision="r"))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = json.loads((self.output / "image-1.text.json").read_text())
        self.assertEqual(text["transcription_review_decision"], "reject_transcription")
        self.assertEqual(text["review_status"], "unreviewed")
        self.assertEqual(text["text"], "Testo sintetico uno")

    def test_cancel_decline_and_eof_never_publish_a_receipt(self):
        for answers, code in [(["q"], 0), (self.answers(final="n"), 0), (["synthetic-transcriber"], 1)]:
            with self.subTest(answers=answers):
                result = self.run_cli(answers)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "existing.txt"
        sentinel.write_text("unchanged")
        result = self.run_cli(self.answers())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(), "unchanged")
        self.assertEqual(list(self.output.iterdir()), [sentinel])

    def test_invalid_selection_parent_and_image_hash_fail_before_prompts(self):
        related = self.payload["acquired_documents_summary"]["items"][0]["related_documents"]
        for mutation in ["duplicate-selection", "missing-id", "duplicate-report", "parent", "image-hash"]:
            with self.subTest(mutation=mutation):
                original = json.loads(json.dumps(self.payload))
                document_ids = self.ids
                if mutation == "duplicate-selection":
                    document_ids = [self.ids[0], self.ids[0]]
                elif mutation == "missing-id":
                    document_ids = ["synthetic:absent"]
                elif mutation == "duplicate-report":
                    related.append(dict(related[0]))
                elif mutation == "parent":
                    related[0]["parent_source_document_id"] = "synthetic:wrong"
                else:
                    related[0]["content_hash"] = "0" * 64
                self.write_report()
                result = self.run_cli(document_ids=document_ids)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Identificativo trascrittore", result.stdout)
                self.assertFalse(self.output.exists())
                self.payload = original
                related = self.payload["acquired_documents_summary"]["items"][0]["related_documents"]

    def test_sidecar_identity_parent_file_and_digest_must_match(self):
        sidecar = self.sidecars[0]
        original = sidecar.read_bytes()
        for mutation in ["identity", "parent", "file", "hash", "eligibility"]:
            with self.subTest(mutation=mutation):
                payload = yaml.safe_load(original)
                if mutation == "identity":
                    payload["document_id"] = "synthetic:wrong"
                elif mutation == "parent":
                    payload["metadata"]["source_document_id"] = "synthetic:wrong"
                elif mutation == "file":
                    payload["file"] = str(self.images[1])
                elif mutation == "hash":
                    payload["metadata"]["content_hash"] = "0" * 64
                else:
                    payload["metadata"]["claim_eligible"] = True
                sidecar.write_text(yaml.safe_dump(payload), encoding="utf-8")
                result = self.run_cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())
                sidecar.write_bytes(original)

    def test_inputs_changed_during_review_cannot_be_attested(self):
        for path in [self.report, self.sidecars[0], self.images[0]]:
            with self.subTest(path=path):
                original = path.read_bytes()
                answers = iter(self.answers())

                def ask(prompt, path=path, original=original, answers=answers):
                    if prompt.startswith("Confermare"):
                        path.write_bytes(original + b" ")
                    return next(answers)

                with self.assertRaises(ValueError):
                    run_document_transcription_wizard(source_report=self.report, document_ids=self.ids,
                                                      output_dir=self.output, input_fn=ask, output_fn=lambda _: None)
                self.assertFalse(self.output.exists())
                path.write_bytes(original)

    def test_no_global_metadata_extraction_and_viewer_is_explicit(self):
        answers = iter(self.answers())
        opened = []
        with patch("caduti_fonti_report.document_analysis.transcription_registration.extract_document_metadata",
                   side_effect=AssertionError("Global metadata extraction is forbidden")):
            result = run_document_transcription_wizard(
                source_report=self.report, document_ids=self.ids, output_dir=self.output,
                open_images=True, open_image_fn=opened.append, input_fn=lambda _: next(answers), output_fn=lambda _: None)
        self.assertEqual(opened, self.images + self.images)
        self.assertTrue(result["review_complete"])

    def test_change_during_staging_and_late_output_creation_fail_closed(self):
        original_write = Path.write_bytes
        original_image = self.images[0].read_bytes()

        def write(path, raw):
            result = original_write(path, raw)
            if path.name == "transcription-manifest.json":
                original_write(self.images[0], original_image + b" ")
            return result

        answers = iter(self.answers())
        with patch.object(Path, "write_bytes", write), self.assertRaises(ValueError):
            run_document_transcription_wizard(source_report=self.report, document_ids=self.ids,
                                              output_dir=self.output, input_fn=lambda _: next(answers),
                                              output_fn=lambda _: None)
        self.assertFalse(self.output.exists())
        self.images[0].write_bytes(original_image)
        answers = iter(self.answers())

        def ask(prompt):
            if prompt.startswith("Confermare"):
                self.output.mkdir()
                (self.output / "other-writer.txt").write_text("preserve")
            return next(answers)

        with self.assertRaises(ValueError):
            run_document_transcription_wizard(source_report=self.report, document_ids=self.ids,
                                              output_dir=self.output, input_fn=ask, output_fn=lambda _: None)
        self.assertEqual((self.output / "other-writer.txt").read_text(), "preserve")
        self.assertFalse((self.output / "transcription-review-receipt.json").exists())

    def test_failed_receipt_write_leaves_no_complete_or_partial_output(self):
        original_open = Path.open

        def failing_open(path, mode="r", *args, **kwargs):
            if path == self.output / "transcription-review-receipt.json" and mode == "xb":
                raise OSError("synthetic disk failure")
            return original_open(path, mode, *args, **kwargs)

        answers = iter(self.answers())
        with patch.object(Path, "open", failing_open), self.assertRaises(OSError):
            run_document_transcription_wizard(source_report=self.report, document_ids=self.ids,
                                              output_dir=self.output, input_fn=lambda _: next(answers),
                                              output_fn=lambda _: None)
        self.assertFalse(self.output.exists())

    def test_installed_help_exposes_only_scoped_options(self):
        result = subprocess.run([str(self.launcher), "documents", "transcription-wizard", "--help"],
                                capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        for option in ["--source-report", "--document-id", "--output-dir", "--open-images"]:
            self.assertIn(option, result.stdout)
        for forbidden in ["--overwrite", "--review-status", "--model", "--apply"]:
            self.assertNotIn(forbidden, result.stdout)


if __name__ == "__main__":
    unittest.main()
