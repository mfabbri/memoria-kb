from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import yaml

from .models import SourceDocument, to_json_safe


def slugify_identifier(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "document"


class RawDocumentStore:
    def __init__(
        self,
        root_dir: Path | str = Path("data/raw"),
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.now_factory = now_factory or (lambda: datetime.now(UTC))

    def save_text_document(
        self,
        *,
        source_id: str,
        title: str,
        url: str,
        text: str,
        media_type: str = "text/plain",
        metadata: dict[str, str] | None = None,
    ) -> SourceDocument:
        access_dt = self._utc_now()
        content_bytes = text.encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        document_id = self._document_id(source_id, title, content_hash[:12])
        document_dir = self._document_dir(source_id, access_dt, document_id)
        document_dir.mkdir(parents=True, exist_ok=True)

        content_path = document_dir / "content.txt"
        content_path.write_bytes(content_bytes)

        document_metadata = dict(metadata or {})
        document_metadata.setdefault("access_mode", "stored_text")
        document = SourceDocument(
            document_id=document_id,
            source_id=source_id,
            title=title,
            url=url,
            access_date=access_dt.isoformat(),
            media_type=media_type,
            local_path=str(content_path),
            content_hash=content_hash,
            raw_text=text,
            metadata=document_metadata,
        )
        self._write_sidecar(document_dir, document)
        return document

    def save_reference_document(
        self,
        *,
        source_id: str,
        title: str,
        url: str,
        reason: str,
        query: str = "",
        metadata: dict[str, str] | None = None,
    ) -> SourceDocument:
        access_dt = self._utc_now()
        seed = "|".join([source_id, title, url, reason, query])
        reference_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        document_id = self._document_id(source_id, title, reference_hash[:12])
        document_dir = self._document_dir(source_id, access_dt, document_id)
        document_dir.mkdir(parents=True, exist_ok=True)

        document_metadata = dict(metadata or {})
        document_metadata.update(
            {
                "access_mode": "reference_only",
                "reason": reason,
                "query": query,
            }
        )
        document = SourceDocument(
            document_id=document_id,
            source_id=source_id,
            title=title,
            url=url,
            access_date=access_dt.isoformat(),
            media_type="text/uri-list",
            local_path="",
            content_hash="",
            raw_text="",
            metadata=document_metadata,
        )
        self._write_sidecar(document_dir, document)
        return document

    def _utc_now(self) -> datetime:
        now = self.now_factory()
        if now.tzinfo is None:
            return now.replace(tzinfo=UTC)
        return now.astimezone(UTC)

    def _document_id(self, source_id: str, title: str, suffix: str) -> str:
        return f"{slugify_identifier(source_id)}-{slugify_identifier(title)}-{suffix}"

    def _document_dir(self, source_id: str, access_dt: datetime, document_id: str) -> Path:
        return self.root_dir / slugify_identifier(source_id) / f"{access_dt:%Y}" / f"{access_dt:%m}" / document_id

    def _write_sidecar(self, document_dir: Path, document: SourceDocument) -> None:
        payload = to_json_safe(document)
        payload["document_dir"] = str(document_dir)
        sidecar_path = document_dir / "document.yaml"
        sidecar_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
