from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import yaml


class ArchivalHtmlCache:
    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir)

    def read(self, url: str) -> str | None:
        html_path = self._html_path(url)
        if not html_path.exists():
            return None
        return html_path.read_text(encoding="utf-8")

    def write(self, *, url: str, html_text: str, metadata: dict[str, str] | None = None) -> Path:
        document_dir = self._document_dir(url)
        document_dir.mkdir(parents=True, exist_ok=True)
        html_path = document_dir / "content.html"
        html_path.write_text(html_text, encoding="utf-8")
        sidecar_path = document_dir / "document.yaml"
        payload = {
            "url": url,
            "html_path": str(html_path),
            "content_hash": hashlib.sha256(html_text.encode("utf-8")).hexdigest(),
            "metadata": dict(metadata or {}),
        }
        sidecar_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return html_path

    def has(self, url: str) -> bool:
        return self._html_path(url).exists()

    def _html_path(self, url: str) -> Path:
        return self._document_dir(url) / "content.html"

    def _document_dir(self, url: str) -> Path:
        parsed = urlparse(url)
        host = parsed.netloc or "unknown-host"
        path_slug = _slugify_path(parsed.path or "/")
        query_hash = hashlib.sha256((parsed.query or "").encode("utf-8")).hexdigest()[:12]
        document_id = f"{path_slug}-{query_hash}"
        return self.root_dir / host / document_id


def _slugify_path(path: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in path)
    tokens = [token for token in cleaned.split("-") if token]
    return "-".join(tokens) or "index"
