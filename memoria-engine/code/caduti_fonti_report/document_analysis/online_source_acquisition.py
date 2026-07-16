from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

from ..models import SourceDocument
from ..renderers import slugify

ImageFetcher = Callable[[str], tuple[bytes, str]]


def acquire_online_source_document(
    *,
    document: SourceDocument,
    root_dir: Path,
    profile_slug: str,
    profile_id: str,
    profile_source_file: str = "",
    review_status: str = "unreviewed",
    image_fetcher: ImageFetcher | None = None,
) -> dict[str, Any]:
    """Persist a detail SourceDocument as an offline-processable raw document."""
    root_dir = Path(root_dir)
    raw_text = (document.raw_text or "").strip()
    source_id = _safe_segment(document.source_id or "unknown_source")
    profile_segment = _safe_segment(profile_slug or profile_id or "unknown_profile")
    target_dir = root_dir / source_id / profile_segment
    target_dir.mkdir(parents=True, exist_ok=True)

    document_slug = _document_slug(document)
    if not raw_text:
        related_documents = _acquire_related_images(
            document=document,
            target_dir=target_dir,
            document_slug=document_slug,
            profile_id=profile_id,
            profile_source_file=profile_source_file,
            review_status=review_status.strip() or "unreviewed",
            image_fetcher=image_fetcher,
        )
        return {
            "status": "skipped_empty_raw_text",
            "source_document_id": document.document_id,
            "source_id": document.source_id,
            "title": document.title,
            "url": document.url,
            "reason": "SourceDocument.raw_text vuoto: nessun documento testuale offline acquisito.",
            "related_documents": related_documents,
            "related_document_count": len([item for item in related_documents if item.get("status") == "acquired"]),
        }

    text_path = target_dir / f"{document_slug}.txt"
    sidecar_path = target_dir / f"{text_path.name}.document.yaml"
    text_path.write_text(raw_text + "\n", encoding="utf-8")

    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    metadata = {
        "document_id": document.document_id,
        "source_id": document.source_id,
        "title": document.title,
        "url": document.url,
        "access_date": document.access_date,
        "document_type": "online_detail_document",
        "media_type": document.media_type or "text/plain",
        "review_status": review_status.strip() or "unreviewed",
        "claim_eligible": True,
        "profile_id": profile_id,
        "profile_source_file": profile_source_file,
        "source_document_id": document.document_id,
        "source_url": document.url,
        "content_hash": content_hash,
        "provenance": "online_source_acquisition",
    }
    for key, value in document.metadata.items():
        if key not in metadata and value not in (None, ""):
            metadata[key] = value

    sidecar = {
        "document_id": document.document_id,
        "source_id": document.source_id,
        "title": document.title,
        "url": document.url,
        "access_date": document.access_date,
        "file": str(text_path),
        "metadata": metadata,
    }
    sidecar_path.write_text(yaml.safe_dump(sidecar, allow_unicode=True, sort_keys=False), encoding="utf-8")
    related_documents = _acquire_related_images(
        document=document,
        target_dir=target_dir,
        document_slug=document_slug,
        profile_id=profile_id,
        profile_source_file=profile_source_file,
        review_status=metadata["review_status"],
        image_fetcher=image_fetcher,
    )

    return {
        "status": "acquired",
        "source_document_id": document.document_id,
        "source_id": document.source_id,
        "title": document.title,
        "url": document.url,
        "profile_id": profile_id,
        "file": str(text_path),
        "sidecar": str(sidecar_path),
        "content_hash": content_hash,
        "review_status": metadata["review_status"],
        "claim_eligible": True,
        "related_documents": related_documents,
        "related_document_count": len([item for item in related_documents if item.get("status") == "acquired"]),
    }


def acquire_online_source_documents(
    *,
    documents: list[SourceDocument],
    root_dir: Path,
    profile_slug: str,
    profile_id: str,
    profile_source_file: str = "",
    review_status: str = "unreviewed",
    image_fetcher: ImageFetcher | None = None,
) -> list[dict[str, Any]]:
    return [
        acquire_online_source_document(
            document=document,
            root_dir=root_dir,
            profile_slug=profile_slug,
            profile_id=profile_id,
            profile_source_file=profile_source_file,
            review_status=review_status,
            image_fetcher=image_fetcher,
        )
        for document in documents
    ]


def acquisition_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    related_status_counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        related_documents = item.get("related_documents", [])
        if not isinstance(related_documents, list):
            continue
        for related_item in related_documents:
            if not isinstance(related_item, dict):
                continue
            related_status = str(related_item.get("status", "unknown"))
            related_status_counts[related_status] = related_status_counts.get(related_status, 0) + 1
    acquired_count = status_counts.get("acquired", 0)
    related_acquired_count = related_status_counts.get("acquired", 0)
    return {
        "count": len(items),
        "acquired_count": acquired_count,
        "related_acquired_count": related_acquired_count,
        "total_acquired_file_count": acquired_count + related_acquired_count,
        "skipped_count": len(items) - acquired_count,
        "status_counts": status_counts,
        "related_status_counts": related_status_counts,
        "items": items,
    }


def _document_slug(document: SourceDocument) -> str:
    base = slugify(document.title or document.document_id or "online-detail")
    digest_source = document.document_id or document.url or document.title
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    return f"{base}-{digest}" if base else f"online-detail-{digest}"


def _safe_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-").lower() or "unknown"


def _acquire_related_images(
    *,
    document: SourceDocument,
    target_dir: Path,
    document_slug: str,
    profile_id: str,
    profile_source_file: str,
    review_status: str,
    image_fetcher: ImageFetcher | None,
) -> list[dict[str, Any]]:
    image_entries = _image_entries_from_metadata(document.metadata)
    if not image_entries:
        return []

    fetcher = image_fetcher or _default_image_fetcher
    related: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, image_entry in enumerate(image_entries, start=1):
        image_url = str(image_entry.get("url", "")).strip()
        if not image_url or image_url in seen:
            continue
        seen.add(image_url)
        try:
            content, media_type = fetcher(image_url)
        except Exception as exc:  # noqa: BLE001 - acquisition reports failed related documents
            related.append(
                {
                    "status": "image_download_failed",
                    "source_document_id": document.document_id,
                    "source_id": document.source_id,
                    "url": image_url,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        if not content:
            related.append(
                {
                    "status": "image_download_failed",
                    "source_document_id": document.document_id,
                    "source_id": document.source_id,
                    "url": image_url,
                    "reason": "download vuoto",
                }
            )
            continue

        media_type = media_type or mimetypes.guess_type(urlparse(image_url).path)[0] or "application/octet-stream"
        extension = _extension_for_image(image_url, media_type)
        image_path = target_dir / f"{document_slug}-image-{index}{extension}"
        sidecar_path = target_dir / f"{image_path.name}.document.yaml"
        image_path.write_bytes(content)

        content_hash = hashlib.sha256(content).hexdigest()
        image_document_id = f"{document.document_id}:image:{index}"
        metadata = {
            "document_id": image_document_id,
            "source_id": document.source_id,
            "title": (image_entry.get("alt") or image_entry.get("title") or f"{document.title} - immagine {index}"),
            "url": image_url,
            "access_date": document.access_date,
            "document_type": "online_detail_image",
            "document_class": "image_scan",
            "media_type": media_type,
            "review_status": review_status,
            "claim_eligible": False,
            "profile_id": profile_id,
            "profile_source_file": profile_source_file,
            "source_document_id": document.document_id,
            "source_url": document.url,
            "image_source_url": image_url,
            "content_hash": content_hash,
            "provenance": "online_source_acquisition",
        }
        sidecar = {
            "document_id": image_document_id,
            "source_id": document.source_id,
            "title": metadata["title"],
            "url": image_url,
            "access_date": document.access_date,
            "file": str(image_path),
            "metadata": metadata,
        }
        sidecar_path.write_text(yaml.safe_dump(sidecar, allow_unicode=True, sort_keys=False), encoding="utf-8")
        related.append(
            {
                "status": "acquired",
                "source_document_id": image_document_id,
                "parent_source_document_id": document.document_id,
                "source_id": document.source_id,
                "title": metadata["title"],
                "url": image_url,
                "file": str(image_path),
                "sidecar": str(sidecar_path),
                "content_hash": content_hash,
                "review_status": review_status,
                "claim_eligible": False,
            }
        )
    return related


def _image_entries_from_metadata(metadata: dict[str, str]) -> list[dict[str, str]]:
    raw_value = metadata.get("partigiani_italia_image_urls_json", "").strip()
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    entries: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        entries.append({"url": url, "alt": str(item.get("alt", "")).strip(), "title": str(item.get("title", "")).strip()})
    return entries


def _default_image_fetcher(url: str) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "ca-di-malanca-source-acquisition/1.0",
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - URL comes from reviewed source detail metadata
        content_type = response.headers.get_content_type() if response.headers else ""
        return response.read(), content_type


def _extension_for_image(url: str, media_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff", ".bmp"}:
        return suffix
    guessed = mimetypes.guess_extension(media_type or "")
    if guessed:
        return guessed
    return ".bin"
