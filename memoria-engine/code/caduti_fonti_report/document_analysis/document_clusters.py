from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

MIN_TOKEN_COUNT = 80
DEFAULT_SIMILARITY_THRESHOLD = 0.86

STOPWORDS = {
    "alla",
    "alle",
    "che",
    "chi",
    "come",
    "con",
    "dei",
    "del",
    "della",
    "delle",
    "dello",
    "dopo",
    "era",
    "gli",
    "ill",
    "nel",
    "nella",
    "nelle",
    "non",
    "per",
    "piu",
    "sul",
    "sulla",
    "tra",
    "una",
}


def find_document_clusters(
    *,
    text_dir: Path,
    output_json: Path | None = None,
    output_md: Path | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    min_token_count: int = MIN_TOKEN_COUNT,
) -> dict[str, Any]:
    threshold = _bounded_threshold(similarity_threshold)
    documents, skipped = _load_documents(text_dir=text_dir, min_token_count=min_token_count)
    edges = _similarity_edges(documents=documents, similarity_threshold=threshold)
    clusters = _clusters_from_edges(documents=documents, edges=edges)

    payload = {
        "@type": "DocumentClusterSet",
        "text_dir": str(text_dir),
        "similarity_method": "tfidf_cosine_pure_python",
        "similarity_threshold": threshold,
        "min_token_count": min_token_count,
        "document_count": len(documents),
        "cluster_count": len(clusters),
        "skipped_count": len(skipped),
        "document_clusters": clusters,
        "skipped_documents": skipped,
    }

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_document_clusters_markdown(payload), encoding="utf-8")

    return payload


def render_document_clusters_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DocumentCluster preview",
        "",
        f"- Metodo: `{payload.get('similarity_method', '')}`",
        f"- Soglia similarita: `{payload.get('similarity_threshold', '')}`",
        f"- Documenti analizzati: `{payload.get('document_count', 0)}`",
        f"- Cluster: `{payload.get('cluster_count', 0)}`",
        f"- Documenti saltati: `{payload.get('skipped_count', 0)}`",
        "",
        "## Cluster documentali",
        "",
    ]
    clusters = payload.get("document_clusters", [])
    if not isinstance(clusters, list) or not clusters:
        lines.append("_Nessun cluster candidato._")
    else:
        for cluster in clusters:
            lines.extend(
                [
                    f"### {cluster.get('cluster_id', '')}",
                    "",
                    f"- Documenti: `{cluster.get('document_count', 0)}`",
                    f"- Similarita media: `{cluster.get('average_similarity', '')}`",
                    f"- Similarita minima: `{cluster.get('min_similarity', '')}`",
                    f"- Similarita massima: `{cluster.get('max_similarity', '')}`",
                    f"- Stato revisione: `{cluster.get('review_status', '')}`",
                    "",
                ]
            )
            for document in cluster.get("documents", []):
                if not isinstance(document, dict):
                    continue
                lines.append(
                    f"- `{document.get('source_document_id', '')}` | "
                    f"{document.get('source_id', '')} | {document.get('document_class', '')}"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _load_documents(*, text_dir: Path, min_token_count: int) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for text_path in sorted(text_dir.rglob("*.text.json")):
        payload = _load_json_object(text_path)
        if not payload:
            skipped.append({"text_file": str(text_path), "reason": "text_unreadable"})
            continue
        if str(payload.get("@type", "")) != "ProcessedDocumentText":
            skipped.append({"text_file": str(text_path), "reason": "unsupported_payload_type"})
            continue
        if str(payload.get("text_status", "")) != "extracted":
            skipped.append(_skip_record(payload=payload, text_path=text_path, reason="text_not_extracted"))
            continue
        tokens = _tokens(str(payload.get("text", "")))
        if len(tokens) < min_token_count:
            skipped.append(_skip_record(payload=payload, text_path=text_path, reason="text_too_short"))
            continue
        documents.append(
            {
                "source_id": str(payload.get("source_id", "")),
                "source_document_id": str(payload.get("source_document_id", "")),
                "document_class": str(payload.get("document_class", "")),
                "review_status": str(payload.get("review_status", "")) or "unreviewed",
                "raw_file": str(payload.get("raw_file", "")),
                "metadata_file": str(payload.get("metadata_file", "")),
                "text_file": str(text_path),
                "text_length": int(payload.get("text_length", 0) or 0),
                "token_count": len(tokens),
                "_term_counts": Counter(tokens),
            }
        )
    return documents, skipped


def _skip_record(*, payload: dict[str, Any], text_path: Path, reason: str) -> dict[str, str]:
    return {
        "source_document_id": str(payload.get("source_document_id", "")),
        "text_file": str(text_path),
        "reason": reason,
    }


def _similarity_edges(*, documents: list[dict[str, Any]], similarity_threshold: float) -> list[dict[str, Any]]:
    vectors = _tfidf_vectors(documents)
    edges: list[dict[str, Any]] = []
    for left_index, left in enumerate(documents):
        for right_index in range(left_index + 1, len(documents)):
            score = _cosine_similarity(vectors[left_index], vectors[right_index])
            if score >= similarity_threshold:
                right = documents[right_index]
                edges.append(
                    {
                        "left": left_index,
                        "right": right_index,
                        "similarity": round(score, 4),
                        "source_document_ids": [
                            str(left.get("source_document_id", "")),
                            str(right.get("source_document_id", "")),
                        ],
                    }
                )
    return edges


def _tfidf_vectors(documents: list[dict[str, Any]]) -> list[dict[str, float]]:
    if not documents:
        return []
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document["_term_counts"].keys()))
    document_count = len(documents)
    vectors: list[dict[str, float]] = []
    for document in documents:
        total_terms = sum(document["_term_counts"].values()) or 1
        vector: dict[str, float] = {}
        for term, count in document["_term_counts"].items():
            tf = count / total_terms
            idf = math.log((1 + document_count) / (1 + document_frequency[term])) + 1
            vector[term] = tf * idf
        vectors.append(vector)
    return vectors


def _clusters_from_edges(*, documents: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adjacency: dict[int, set[int]] = defaultdict(set)
    edge_by_pair: dict[tuple[int, int], dict[str, Any]] = {}
    for edge in edges:
        left = int(edge["left"])
        right = int(edge["right"])
        adjacency[left].add(right)
        adjacency[right].add(left)
        edge_by_pair[(min(left, right), max(left, right))] = edge

    clusters: list[dict[str, Any]] = []
    visited: set[int] = set()
    for start in sorted(adjacency):
        if start in visited:
            continue
        stack = [start]
        component: set[int] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(sorted(adjacency[current] - component))
        visited.update(component)
        if len(component) < 2:
            continue
        component_edges = [
            edge
            for (left, right), edge in edge_by_pair.items()
            if left in component and right in component
        ]
        scores = [float(edge["similarity"]) for edge in component_edges]
        cluster_documents = [_document_preview(documents[index]) for index in sorted(component)]
        clusters.append(
            {
                "@type": "DocumentCluster",
                "@id": _cluster_id(cluster_documents),
                "cluster_id": _cluster_id(cluster_documents),
                "document_count": len(cluster_documents),
                "documents": cluster_documents,
                "pairwise_similarities": [
                    {
                        "source_document_ids": edge["source_document_ids"],
                        "similarity": edge["similarity"],
                    }
                    for edge in component_edges
                ],
                "min_similarity": round(min(scores), 4),
                "max_similarity": round(max(scores), 4),
                "average_similarity": round(sum(scores) / len(scores), 4),
                "confidence": round(sum(scores) / len(scores), 4),
                "reasons": ["tfidf_cosine_similarity_above_threshold"],
                "review_status": "unreviewed",
            }
        )
    return clusters


def _document_preview(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": str(document.get("source_id", "")),
        "source_document_id": str(document.get("source_document_id", "")),
        "document_class": str(document.get("document_class", "")),
        "review_status": str(document.get("review_status", "")) or "unreviewed",
        "raw_file": str(document.get("raw_file", "")),
        "metadata_file": str(document.get("metadata_file", "")),
        "text_file": str(document.get("text_file", "")),
        "text_length": int(document.get("text_length", 0) or 0),
        "token_count": int(document.get("token_count", 0) or 0),
    }


def _cluster_id(documents: list[dict[str, Any]]) -> str:
    parts = sorted(str(document.get("source_document_id", "")) for document in documents)
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"document-cluster:{digest}"


def _cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    common_terms = set(left) & set(right)
    numerator = sum(left[term] * right[term] for term in common_terms)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return [
        token
        for token in re.findall(r"[a-z0-9]+", ascii_text)
        if len(token) >= 3 and token not in STOPWORDS
    ]


def _bounded_threshold(value: float) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError):
        return DEFAULT_SIMILARITY_THRESHOLD
    return min(1.0, max(0.0, threshold))


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera DocumentCluster preview-only da testi processati.")
    parser.add_argument("--text-dir", default="data/processed/documents")
    parser.add_argument("--output-json", default="risultati/document_analysis/document_clusters.json")
    parser.add_argument("--output-md", default="risultati/document_analysis/document_clusters.md")
    parser.add_argument("--similarity-threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    parser.add_argument("--min-token-count", type=int, default=MIN_TOKEN_COUNT)
    args = parser.parse_args()

    payload = find_document_clusters(
        text_dir=Path(args.text_dir),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        similarity_threshold=args.similarity_threshold,
        min_token_count=args.min_token_count,
    )
    print(f"DocumentCluster JSON scritto in {args.output_json}")
    print(f"DocumentCluster Markdown scritto in {args.output_md}")
    print(f"Cluster: {payload['cluster_count']}")
    print(f"Documenti saltati: {payload['skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
