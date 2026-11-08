from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .legacy_sources import is_legacy_profile_seed_source


def migrate_legacy_profile_seeds(
    *,
    profiles_index: Path,
    output_dir: Path,
    expected_legacy_count: int,
    apply: bool = False,
) -> dict[str, Any]:
    """Detach legacy CSV seeds while preserving byte-exact originals in an audit."""
    if expected_legacy_count < 1:
        raise ValueError("expected_legacy_count deve essere positivo.")
    index_bytes = profiles_index.read_bytes()
    index = _load_json_object(index_bytes, label="indice profili")
    entries = index.get("profiles")
    if not isinstance(entries, list):
        raise ValueError("Indice profili non valido: profiles deve essere una lista.")

    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    profiles: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Indice profili non valido: entry non-oggetto.")
        profile_id = str(entry.get("@id", "")).strip()
        filename = str(entry.get("file", "")).strip()
        if not profile_id or not filename:
            raise ValueError("Indice profili non valido: @id e file sono obbligatori.")
        if profile_id in seen_ids or filename in seen_files:
            raise ValueError("Indice profili non valido: ID o file duplicato.")
        seen_ids.add(profile_id)
        seen_files.add(filename)
        profile_path = (profiles_index.parent / filename).resolve()
        if profile_path.parent != profiles_index.parent.resolve():
            raise ValueError(f"Path profilo fuori directory: {filename}")
        raw = profile_path.read_bytes()
        payload = _load_json_object(raw, label=f"profilo {profile_id}")
        if str(payload.get("@id", "")).strip() != profile_id:
            raise ValueError(f"ID profilo non concorde con l'indice: {profile_id}")
        seed = payload.get("seed")
        if not isinstance(seed, dict) or not is_legacy_profile_seed_source(str(seed.get("source", ""))):
            continue
        profiles.append(
            {
                "profile_id": profile_id,
                "profile_path": str(profile_path),
                "original_bytes": raw,
                "original_payload": payload,
                "original_seed": seed,
                "original_sha256": _sha256(raw),
            }
        )

    if not profiles:
        migrated = [
            (str(entry.get("@id", "")), str(entry.get("file", "")))
            for entry in entries
            if isinstance(entry, dict)
        ]
        migration_ids = set()
        for profile_id, filename in migrated:
            payload = _load_json_object((profiles_index.parent / filename).read_bytes(), label=profile_id)
            seed = payload.get("seed", {})
            metadata = payload.get("metadata", {})
            if isinstance(seed, dict) and seed.get("source") == "profile_seed_migration":
                if isinstance(metadata, dict) and metadata.get("profile_seed_migration_id"):
                    migration_ids.add(str(metadata["profile_seed_migration_id"]))
        prior_audit = output_dir / "profile-seed-migration.audit.json"
        if len(migration_ids) == 1 and prior_audit.is_file():
            prior = json.loads(prior_audit.read_text(encoding="utf-8"))
            if prior.get("migration_id") in migration_ids and prior.get("status") == "applied":
                if _sha256(index_bytes) != prior.get("profiles_index_sha256"):
                    raise ValueError("Indice profili diverso da quello della migrazione applicata.")
                audited_profiles = {item.get("profile_id"): item for item in prior.get("profiles", [])}
                migrated_ids: set[str] = set()
                for profile_id, filename in migrated:
                    payload = _load_json_object(
                        (profiles_index.parent / filename).read_bytes(),
                        label=profile_id,
                    )
                    metadata = payload.get("metadata", {})
                    if isinstance(metadata, dict) and metadata.get("profile_seed_migration_id") == prior.get("migration_id"):
                        migrated_ids.add(profile_id)
                if migrated_ids != set(audited_profiles):
                    raise ValueError("I profili migrati non corrispondono all'audit applicato.")
                for profile_id, record in audited_profiles.items():
                    current = Path(str(record.get("profile_path", ""))).read_bytes()
                    if _sha256(current) != record.get("after_sha256"):
                        raise ValueError(f"Profilo migrato modificato dopo l'audit: {profile_id}")
                prior["previously_migrated_count"] = int(prior.get("migrated_count", 0))
                prior["status"] = "already_applied"
                prior["legacy_profile_count"] = 0
                prior["migrated_count"] = 0
                return prior
    if len(profiles) != expected_legacy_count:
        raise ValueError(
            f"Conteggio seed legacy diverso dal previsto: attesi {expected_legacy_count}, trovati {len(profiles)}."
        )

    migration_digest = hashlib.sha256(
        index_bytes + b"\n" + b"\n".join(
            f"{item['profile_id']}:{item['original_sha256']}".encode()
            for item in sorted(profiles, key=lambda value: value["profile_id"])
        )
    ).hexdigest()
    migration_id = f"profile-seed-migration:{migration_digest[:20]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = output_dir / "backups"
    profile_records: list[dict[str, Any]] = []
    for item in profiles:
        after_payload = json.loads(json.dumps(item["original_payload"], ensure_ascii=False))
        after_seed = after_payload["seed"]
        after_seed["source"] = "profile_seed_migration"
        after_seed["source_id"] = migration_id
        after_seed["payload"] = {}
        metadata = after_payload.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError(f"Metadata profilo non-oggetto: {item['profile_id']}")
        metadata["profile_seed_migration_id"] = migration_id
        output_bytes = (json.dumps(after_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        profile_records.append(
            {
                "profile_id": item["profile_id"],
                "profile_path": item["profile_path"],
                "before_sha256": item["original_sha256"],
                "after_sha256": _sha256(output_bytes),
                "original_seed": item["original_seed"],
                "output_bytes": output_bytes,
            }
        )

    verified_fact_count = sum(
        len(item["original_payload"].get("verified_facts", []))
        if isinstance(item["original_payload"].get("verified_facts", []), list)
        else len(item["original_payload"].get("verified_facts", {}))
        if isinstance(item["original_payload"].get("verified_facts", {}), dict)
        else 0
        for item in profiles
    )
    audit: dict[str, Any] = {
        "@type": "LegacyProfileSeedMigrationAudit",
        "migration_id": migration_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "preview" if not apply else "prepared",
        "profiles_index": str(profiles_index.resolve()),
        "profiles_index_sha256": _sha256(index_bytes),
        "expected_legacy_count": expected_legacy_count,
        "legacy_profile_count": len(profile_records),
        "migrated_count": 0,
        "verified_fact_count_before": verified_fact_count,
        "verified_fact_count_after": verified_fact_count,
        "writes_canonical_profiles": apply,
        "backup_dir": str(backup_dir.resolve()) if apply else "",
        "profiles": [
            {key: value for key, value in record.items() if key != "output_bytes"}
            for record in profile_records
        ],
        "notes": [
            "La migrazione modifica solo il seed di importazione e i metadati di audit del profilo.",
            "Il payload CSV viene conservato nel backup e nell'audit, non nel profilo attivo.",
            "Nessun verified_fact, review_status, profile_status o publication_status viene promosso o alterato.",
        ],
    }
    if not apply:
        audit["status"] = "preview"
        _write_audit(output_dir, audit)
        return audit

    backup_dir.mkdir(parents=True, exist_ok=True)
    backups: list[tuple[Path, bytes]] = []
    for item in profiles:
        backup_path = backup_dir / f"{item['profile_id'].rsplit(':', 1)[-1]}.{item['original_sha256']}.jsonld"
        if backup_path.exists():
            backup_bytes = backup_path.read_bytes()
            if _sha256(backup_bytes) != item["original_sha256"]:
                raise ValueError(f"Backup preesistente con hash divergente: {backup_path}")
        else:
            backup_path.write_bytes(item["original_bytes"])
        backups.append((backup_path, item["original_bytes"]))
        if _sha256(backup_path.read_bytes()) != item["original_sha256"]:
            raise ValueError(f"Verifica backup fallita: {backup_path}")
        next(record for record in profile_records if record["profile_id"] == item["profile_id"])["backup_path"] = str(backup_path)
    record_by_id = {record["profile_id"]: record for record in profile_records}
    for audit_record in audit["profiles"]:
        audit_record["backup_path"] = record_by_id[audit_record["profile_id"]].get("backup_path", "")

    _write_audit(output_dir, audit)
    written_records: list[dict[str, Any]] = []
    try:
        for record in profile_records:
            profile_path = Path(record["profile_path"])
            current = profile_path.read_bytes()
            if _sha256(current) != record["before_sha256"]:
                raise ValueError(f"Profilo modificato dopo il preflight: {profile_path}")
            _atomic_write(profile_path, record["output_bytes"])
            if _sha256(profile_path.read_bytes()) != record["after_sha256"]:
                raise ValueError(f"Verifica post-write fallita: {profile_path}")
            written_records.append(record)
        audit["status"] = "applied"
        audit["migrated_count"] = len(profile_records)
        _write_audit(output_dir, audit)
    except Exception:
        for record in reversed(written_records):
            profile_path = Path(record["profile_path"])
            item = next(item for item in profiles if item["profile_id"] == record["profile_id"])
            if profile_path.exists() and _sha256(profile_path.read_bytes()) == record["after_sha256"]:
                _atomic_write(profile_path, item["original_bytes"])
        audit["status"] = "rolled_back_after_error"
        _write_audit(output_dir, audit)
        raise
    return audit


def _write_audit(output_dir: Path, audit: dict[str, Any]) -> None:
    safe = json.loads(json.dumps(audit, ensure_ascii=False))
    for item in safe.get("profiles", []):
        original_seed = item.get("original_seed")
        if isinstance(original_seed, dict):
            item["original_seed_sha256"] = _sha256(
                json.dumps(original_seed, ensure_ascii=False, sort_keys=True).encode("utf-8")
            )
    filename = "profile-seed-migration.audit.json" if safe.get("writes_canonical_profiles") else "profile-seed-migration.preview.json"
    output = output_dir / filename
    output.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _load_json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"JSON non valido: {label}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON non-oggetto: {label}")
    return payload


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
