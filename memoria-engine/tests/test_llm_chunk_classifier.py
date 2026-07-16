from __future__ import annotations

import hashlib
import json
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from caduti_fonti_report.document_analysis.llm_chunk_classifier import (  # noqa: E402
    classify_document_chunks,
    chunk_classification_schema_path,
    render_llm_chunk_classifications_markdown,
    _parse_ollama_api_response,
    _parse_llm_json,
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


def write_chunks_payload(
    root_dir: Path,
    *,
    source_document_id: str = "doc:chunks",
    chunks: list[dict[str, object]],
) -> Path:
    source_id = "manual_uploads"
    chunk_dir = root_dir / source_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    path = chunk_dir / f"{source_document_id.replace(':', '-')}.chunks.json"
    payload = {
        "@type": "PhysicalDocumentChunkDocument",
        "source_id": source_id,
        "source_document_id": source_document_id,
        "document_class": "word_document",
        "review_status": "unreviewed",
        "text_file": "doc.text.json",
        "text_sha256": "source-sha",
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def chunk_payload(*, chunk_index: int, text: str, text_quality_warnings: list[str] | None = None) -> dict[str, object]:
    chunk_id = f"physical-document-chunk:{chunk_index}"
    return {
        "@type": "PhysicalDocumentChunk",
        "@id": chunk_id,
        "chunk_id": chunk_id,
        "source_id": "manual_uploads",
        "source_document_id": "doc:chunks",
        "text_file": "doc.text.json",
        "source_text_sha256": "source-sha",
        "chunk_index": chunk_index,
        "char_start": 0,
        "char_end": len(text),
        "token_estimate": len(text.split()),
        "overlap_previous": False,
        "overlap_next": False,
        "text": text,
        "chunk_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "extraction_method": "fixed_window_chunking",
        "boundary_strategy": "sentence_near_limit",
        "boundary_adjusted": True,
        "boundary_reason": "sentence_boundary_before_max_chars",
        "text_quality_warnings": text_quality_warnings or [],
        "review_status": "unreviewed",
    }


class LlmChunkClassifierTests(unittest.TestCase):
    def test_classifies_chunks_preview_only_with_provenance(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            output_dir = tmp_dir / "classifications"
            output_json = tmp_dir / "llm_chunk_classifications.json"
            output_md = tmp_dir / "llm_chunk_classifications.md"
            write_chunks_payload(
                chunk_dir,
                chunks=[
                    chunk_payload(
                        chunk_index=1,
                        text=(
                            "Andreoli Dino Dati: nato a Bologna. Morto a Ca' di Malanca nel 1944. "
                            "Partigiano della 36ª Brigata Garibaldi."
                        ),
                    ),
                    chunk_payload(
                        chunk_index=2,
                        text="La battaglia di Purocielo vide combattimenti, mortai tedeschi e rastrellamenti.",
                    ),
                ],
            )

            payload = classify_document_chunks(
                chunk_dir=chunk_dir,
                output_dir=output_dir,
                output_json=output_json,
                output_md=output_md,
                model_name="fake-local-llm",
            )
            sidecar = json.loads(
                (output_dir / "manual_uploads" / "doc-chunks.llm-chunk-classifications.json").read_text("utf-8")
            )
            output_json_exists = output_json.exists()
            output_md_exists = output_md.exists()

        classifications = payload["documents"][0]["classifications"]
        self.assertEqual(payload["@type"], "LLMChunkClassificationSet")
        self.assertEqual(payload["document_count"], 1)
        self.assertEqual(payload["classification_count"], 2)
        self.assertEqual(sidecar["classification_count"], 2)
        self.assertTrue(output_json_exists)
        self.assertTrue(output_md_exists)
        self.assertEqual(classifications[0]["@type"], "LLMChunkClassification")
        self.assertEqual(classifications[0]["classification_type"], "person_biographical_entry")
        self.assertEqual(classifications[0]["chunk_id"], "physical-document-chunk:1")
        self.assertIn("Andreoli Dino", classifications[0]["mentioned_people"])
        self.assertIn("Ca' di Malanca", classifications[0]["mentioned_places"])
        self.assertEqual(classifications[0]["review_status"], "unreviewed")
        self.assertEqual(classifications[0]["recommended_use"], "search_hint")
        self.assertEqual(classifications[0]["provider"], "fake")
        self.assertEqual(classifications[1]["classification_type"], "battle_context")
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("EvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))
        self.assertNotIn("ProfilePatch", json.dumps(payload))

    def test_marks_unclear_chunks_for_manual_review_without_claims(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunks_payload(
                chunk_dir,
                chunks=[chunk_payload(chunk_index=1, text="Frammento breve senza segnali forti.")],
            )

            payload = classify_document_chunks(chunk_dir=chunk_dir)

        classification = payload["documents"][0]["classifications"][0]
        self.assertEqual(classification["classification_type"], "unclear")
        self.assertEqual(classification["recommended_use"], "manual_review_required")
        self.assertIn("manual_review_recommended", classification["warnings"])
        self.assertIn("llm_output_unreviewed", classification["warnings"])
        self.assertEqual(classification["review_status"], "unreviewed")

    def test_propagates_chunk_text_quality_warnings(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunks_payload(
                chunk_dir,
                chunks=[
                    chunk_payload(
                        chunk_index=1,
                        text="Brigata Garibaldi nel documento.",
                        text_quality_warnings=["encoding_suspect_mojibake"],
                    )
                ],
            )

            payload = classify_document_chunks(chunk_dir=chunk_dir)

        classification = payload["documents"][0]["classifications"][0]
        self.assertIn("encoding_suspect_mojibake", classification["warnings"])
        self.assertIn("llm_output_unreviewed", classification["warnings"])

    def test_normalizes_llm_warning_string_without_splitting_letters(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunks_payload(
                chunk_dir,
                chunks=[chunk_payload(chunk_index=1, text="Battaglia di Purocielo, 1944.")],
            )
            completed = Mock()
            completed.returncode = 0
            completed.stdout = json.dumps(
                {
                    "model": "gemma3:4b",
                    "response": json.dumps(
                        {
                            "classification_type": "battle_context",
                            "mentioned_people": ["Nome Cognome"],
                            "mentioned_places": ["Purocielo"],
                            "mentioned_dates": ["1944"],
                            "confidence": 0.72,
                            "reasons": "battle_context_signal",
                            "warnings": "The text needs review.",
                            "recommended_use": "search_hint",
                            "review_status": "unreviewed",
                        }
                    ),
                    "done": True,
                }
            )
            completed.stderr = ""

            with patch("caduti_fonti_report.document_analysis.llm_chunk_classifier.subprocess.run", return_value=completed):
                payload = classify_document_chunks(chunk_dir=chunk_dir, provider="ollama-wsl")

        classification = payload["documents"][0]["classifications"][0]
        self.assertIn("The text needs review.", classification["warnings"])
        self.assertNotIn("T", classification["warnings"])
        self.assertEqual(classification["reasons"], ["battle_context_signal"])

    def test_crowded_llm_chunk_is_triage_only(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunks_payload(
                chunk_dir,
                chunks=[chunk_payload(chunk_index=1, text="Molte persone citate nel documento.")],
            )
            completed = Mock()
            completed.returncode = 0
            completed.stdout = json.dumps(
                {
                    "model": "gemma3:4b",
                    "response": json.dumps(
                        {
                            "classification_type": "narrative_context",
                            "mentioned_people": [f"Persona {idx}" for idx in range(8)],
                            "mentioned_places": [],
                            "mentioned_dates": [],
                            "confidence": 0.9,
                            "reasons": [],
                            "warnings": [],
                            "recommended_use": "search_hint",
                            "review_status": "unreviewed",
                        }
                    ),
                    "done": True,
                }
            )
            completed.stderr = ""

            with patch("caduti_fonti_report.document_analysis.llm_chunk_classifier.subprocess.run", return_value=completed):
                payload = classify_document_chunks(chunk_dir=chunk_dir, provider="ollama-wsl")

        classification = payload["documents"][0]["classifications"][0]
        self.assertEqual(classification["classification_type"], "multi_person_biographical_list")
        self.assertIn("many_people_in_chunk", classification["warnings"])
        self.assertIn("multi_person_biographical_list_triage_only", classification["warnings"])
        self.assertEqual(classification["recommended_use"], "triage_only")
        self.assertEqual(classification["review_status"], "unreviewed")
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_fake_provider_marks_multi_person_biographical_list_as_triage_only(self) -> None:
        names = [
            "Andreoli Dino",
            "Rossi Mario",
            "Bianchi Luigi",
            "Neri Paolo",
            "Verdi Carlo",
            "Galli Pietro",
            "Conti Bruno",
            "Ricci Enzo",
        ]
        text = "Dati biografici: " + "; ".join(f"{name} nato nel 1920" for name in names)
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunks_payload(
                chunk_dir,
                chunks=[chunk_payload(chunk_index=1, text=text)],
            )

            payload = classify_document_chunks(chunk_dir=chunk_dir)

        classification = payload["documents"][0]["classifications"][0]
        self.assertEqual(classification["classification_type"], "multi_person_biographical_list")
        self.assertEqual(classification["recommended_use"], "triage_only")
        self.assertIn("many_people_in_chunk", classification["warnings"])
        self.assertIn("multi_person_biographical_list_triage_only", classification["warnings"])
        self.assertIn("multi_person_biographical_list_signals", classification["reasons"])
        self.assertEqual(classification["review_status"], "unreviewed")
        self.assertNotIn("CandidateEvidenceClaim", json.dumps(payload))
        self.assertNotIn("ProfilePatch", json.dumps(payload))
        self.assertNotIn("verified_facts", json.dumps(payload))

    def test_chunk_classification_schema_allows_multi_person_biographical_list(self) -> None:
        schema_path = chunk_classification_schema_path()
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        classification_types = schema["properties"]["classification_type"]["enum"]

        self.assertIn("memoria-rules", schema_path.parts)
        self.assertNotIn("ricerche", schema_path.parts)
        self.assertIn("multi_person_biographical_list", classification_types)

    def test_unsupported_provider_becomes_manual_review(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunks_payload(
                chunk_dir,
                chunks=[chunk_payload(chunk_index=1, text="Brigata Garibaldi nel documento.")],
            )

            payload = classify_document_chunks(chunk_dir=chunk_dir, provider="not-supported")

        classification = payload["documents"][0]["classifications"][0]
        self.assertEqual(classification["classification_type"], "manual_review_required")
        self.assertEqual(classification["recommended_use"], "manual_review_required")
        self.assertIn("unsupported_llm_provider:not-supported", classification["warnings"])

    def test_parse_llm_json_from_wrapped_output(self) -> None:
        parsed = _parse_llm_json(
            'Ecco il JSON:\n{"classification_type":"battle_context","mentioned_people":[],"mentioned_places":["Purocielo"],'
            '"mentioned_dates":["1944"],"confidence":0.71,"reasons":["battle"],"warnings":[],"recommended_use":"search_hint",'
            '"review_status":"unreviewed"}'
        )

        self.assertEqual(parsed["classification_type"], "battle_context")
        self.assertEqual(parsed["mentioned_places"], ["Purocielo"])

    def test_parse_llm_json_from_json_encoded_string(self) -> None:
        encoded = json.dumps(
            '{"classification_type":"formation_context","mentioned_people":[],"mentioned_places":[],"mentioned_dates":[],'
            '"confidence":0.61,"reasons":["formation"],"warnings":[],"recommended_use":"search_hint",'
            '"review_status":"unreviewed"}'
        )

        parsed = _parse_llm_json(encoded)

        self.assertEqual(parsed["classification_type"], "formation_context")

    def test_parse_ollama_api_response_field(self) -> None:
        payload = json.dumps(
            {
                "model": "gemma3:4b",
                "response": json.dumps(
                    {
                        "classification_type": "unclear",
                        "mentioned_people": [],
                        "mentioned_places": [],
                        "mentioned_dates": [],
                        "confidence": 0.2,
                        "reasons": ["diagnostic_test"],
                        "warnings": [],
                        "recommended_use": "manual_review_required",
                        "review_status": "unreviewed",
                    }
                ),
                "done": True,
            }
        )

        parsed = _parse_ollama_api_response(payload)

        self.assertEqual(parsed["classification_type"], "unclear")
        self.assertEqual(parsed["reasons"], ["diagnostic_test"])

    def test_ollama_wsl_provider_uses_json_format_and_stdin_prompt(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunks_payload(
                chunk_dir,
                chunks=[chunk_payload(chunk_index=1, text="Battaglia di Purocielo, 1944.")],
            )
            completed = Mock()
            completed.returncode = 0
            completed.stdout = json.dumps(
                {
                    "model": "gemma3:4b",
                    "response": json.dumps(
                        {
                            "classification_type": "battle_context",
                            "mentioned_people": [],
                            "mentioned_places": ["Purocielo"],
                            "mentioned_dates": ["1944"],
                            "confidence": 0.72,
                            "reasons": ["battle_context_signal"],
                            "warnings": [],
                            "recommended_use": "search_hint",
                            "review_status": "unreviewed",
                        }
                    ),
                    "done": True,
                }
            )
            completed.stderr = ""

            with patch("caduti_fonti_report.document_analysis.llm_chunk_classifier.subprocess.run", return_value=completed) as run:
                payload = classify_document_chunks(
                    chunk_dir=chunk_dir,
                    provider="ollama-wsl",
                    model_name="gemma3:4b",
                    wsl_distribution="Ubuntu",
                )

        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            [
                "wsl",
                "-d",
                "Ubuntu",
                "-e",
                "curl",
                "-sS",
                "http://127.0.0.1:11434/api/generate",
                "-H",
                "Content-Type: application/json",
                "--data-binary",
                "@-",
            ],
        )
        request_payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(request_payload["model"], "gemma3:4b")
        self.assertEqual(request_payload["format"], "json")
        self.assertFalse(request_payload["stream"])
        self.assertIn("Battaglia di Purocielo", request_payload["prompt"])
        classification = payload["documents"][0]["classifications"][0]
        self.assertEqual(classification["classification_type"], "battle_context")
        self.assertEqual(classification["provider"], "ollama-wsl")
        self.assertIn("Purocielo", classification["mentioned_places"])

    def test_ollama_wsl_invalid_json_keeps_diagnostic_excerpt(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            write_chunks_payload(
                chunk_dir,
                chunks=[chunk_payload(chunk_index=1, text="Battaglia di Purocielo, 1944.")],
            )
            completed = Mock()
            completed.returncode = 0
            completed.stdout = "\x1b[?25lNon e' JSON valido per la classificazione.\x1b[?25h"
            completed.stderr = ""

            with patch("caduti_fonti_report.document_analysis.llm_chunk_classifier.subprocess.run", return_value=completed):
                payload = classify_document_chunks(chunk_dir=chunk_dir, provider="ollama-wsl")

        classification = payload["documents"][0]["classifications"][0]
        self.assertEqual(classification["classification_type"], "manual_review_required")
        self.assertIn("ollama_wsl_invalid_json", classification["warnings"])
        self.assertIn("Non e' JSON valido", classification["provider_diagnostics"]["stdout_excerpt"])

    def test_skips_invalid_chunk_documents(self) -> None:
        with workspace_temp_dir() as tmp_dir:
            chunk_dir = tmp_dir / "chunks"
            invalid_dir = chunk_dir / "manual_uploads"
            invalid_dir.mkdir(parents=True)
            (invalid_dir / "invalid.chunks.json").write_text(
                json.dumps({"@type": "OtherPayload", "chunks": []}),
                encoding="utf-8",
            )

            payload = classify_document_chunks(chunk_dir=chunk_dir)

        self.assertEqual(payload["document_count"], 0)
        self.assertEqual(payload["classification_count"], 0)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["skipped_documents"][0]["reason"], "unsupported_payload_type")

    def test_markdown_renderer_lists_classifications_for_review(self) -> None:
        payload = {
            "classification_method": "fake_local_llm_chunk_classification",
            "model_name": "fake-local-llm",
            "prompt_version": "chunk-classification-v1",
            "document_count": 1,
            "classification_count": 1,
            "skipped_count": 0,
            "documents": [
                {
                    "source_document_id": "doc:1",
                    "source_id": "manual_uploads",
                    "review_status": "unreviewed",
                    "classification_count": 1,
                    "chunk_file": "doc.chunks.json",
                    "classifications": [
                        {
                            "classification_id": "llm-chunk-classification:abc",
                            "classification_type": "battle_context",
                            "chunk_index": 1,
                            "confidence": 0.7,
                            "recommended_use": "search_hint",
                        }
                    ],
                }
            ],
        }

        markdown = render_llm_chunk_classifications_markdown(payload)

        self.assertIn("# LLMChunkClassification preview", markdown)
        self.assertIn("llm-chunk-classification:abc", markdown)
        self.assertIn("battle_context", markdown)
        self.assertIn("unreviewed", markdown)


if __name__ == "__main__":
    unittest.main()
