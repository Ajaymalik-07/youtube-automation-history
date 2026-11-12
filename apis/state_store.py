"""
Authoritative Persistent State Store & Synchronization Engine (Phase 23)

Provides a free, zero-paid-dependency persistent storage architecture uniting
local execution and ephemeral GitHub Actions runners:

1. Authoritative Storage Files (git-tracked JSON state in output/ + local SQLite WAL ledger):
   - output/production_database.json        (18-stage production job records)
   - output/historical_performance_db.json  (Immutable Analytics & snapshot history)
   - output/automation_schedule.json        (Daily IST slot status & history_runs)
   - output/growth_experiments.json         (Controlled experiment definitions & samples)
   - output/pending_uploads/upload_*.json   (Recoverable upload retry manifests)
   - output/state_manifest.json             (Schema versions, monotonic revisions & sync metadata)
   - output/yaas_state.sqlite               (Local ACID SQLite WAL mirror & crash recovery)
   - output/backups/<label>_<ts>/           (Checksummed timestamped backups)

   Note: GitHub Actions cache (`actions/cache`) is ONLY used as a transient media/queue
   cache for large rendered `.mp4` files and NEVER as the authoritative database.

2. Schema Versioning & Migrations (CURRENT_SCHEMA_VERSION = 2):
   - Transparently migrates legacy v1 flat dictionaries & legacy `analytics_snapshots.json`.
   - Adds monotonic `revision` integers and UTC `updated_at` timestamps to prevent stale-state overwrites.

3. Safe Concurrency & Reconciliation Sync:
   - Cross-process file locks (`CrossProcessFileLock`) + atomic `os.replace()`.
   - Deterministic monotonic merge (`merge_production_records`, `merge_growth_records`, `merge_schedule_states`).
"""
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import config
from uploader.safety import (
    LEGACY_STATE_MAPPING,
    CrossProcessFileLock,
    PublishingState,
)

CURRENT_SCHEMA_VERSION = 2

STATE_FILES = (
    "production_database.json",
    "historical_performance_db.json",
    "automation_schedule.json",
    "growth_experiments.json",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(ts: Optional[str]) -> datetime:
    if not ts:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _atomic_write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    tmp_path = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEMA VERSIONING & MIGRATIONS (v1 -> v2)
# ══════════════════════════════════════════════════════════════════════════════

def migrate_production_records(raw: Any) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Migrates legacy v1 flat dict or wrapped v2 production database into normalized v2 records.
    Returns (records_dict, migration_info).
    """
    migrated_count = 0
    if not isinstance(raw, dict):
        return {}, {"source_version": 0, "target_version": CURRENT_SCHEMA_VERSION, "migrated_records": 0}

    if "records" in raw and isinstance(raw.get("records"), dict) and "schema_version" in raw:
        source_version = int(raw.get("schema_version", 1))
        source_records = raw["records"]
    else:
        source_version = 1
        source_records = raw

    normalized: Dict[str, Dict[str, Any]] = {}
    for k, rec in source_records.items():
        if not isinstance(rec, dict):
            continue
        out = dict(rec)
        curr = str(out.get("current_state", PublishingState.TOPIC_SELECTED.value))
        mapped = LEGACY_STATE_MAPPING.get(curr, curr)
        if mapped != curr or int(out.get("schema_version", 1)) < CURRENT_SCHEMA_VERSION:
            migrated_count += 1
        out["current_state"] = mapped
        out["schema_version"] = CURRENT_SCHEMA_VERSION
        out["revision"] = max(1, int(out.get("revision", 1) or 1))
        out.setdefault("updated_at", out.get("created_at") or _now_iso())
        out.setdefault("history", [])
        out.setdefault("metadata", {})
        out.setdefault("retry_count", 0)
        out.setdefault("recovered_count", 0)
        norm_key = os.path.normpath(out.get("video_path") or k)
        normalized[norm_key] = out

    return normalized, {
        "source_version": source_version,
        "target_version": CURRENT_SCHEMA_VERSION,
        "migrated_records": migrated_count,
        "total_records": len(normalized),
    }


def migrate_growth_records(raw: Any) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Migrates v1 `historical_performance_db.json` (or legacy `analytics_snapshots.json`) to v2 schema.
    Ensures `None` unavailable metrics are never coerced to 0 and snapshot histories remain intact.
    """
    migrated_count = 0
    if not isinstance(raw, dict):
        return {}, {"source_version": 0, "target_version": CURRENT_SCHEMA_VERSION, "migrated_records": 0}

    if "records" in raw and isinstance(raw.get("records"), dict) and "schema_version" in raw:
        source_version = int(raw.get("schema_version", 1))
        source_records = raw["records"]
    else:
        source_version = 1
        source_records = raw

    normalized: Dict[str, Dict[str, Any]] = {}
    for vid, rec in source_records.items():
        if not isinstance(rec, dict):
            continue
        out = dict(rec)
        if int(out.get("schema_version", 1)) < CURRENT_SCHEMA_VERSION or "metrics" in out:
            migrated_count += 1

        # Handle legacy analytics_snapshots.json format cleanly
        if "metrics" in out and "latest_metrics" not in out:
            m = out.get("metrics", {}) or {}
            out = {
                "video_id": vid,
                "channel_id": out.get("channel_id") or getattr(config, "YOUTUBE_CHANNEL_ID", ""),
                "video_format": "short" if out.get("is_shorts") else "longform",
                "topic": out.get("topic") or out.get("title") or "Historical Topic",
                "content_pillar": out.get("pillar_name") or "General History",
                "publication_timestamp": out.get("published_at", ""),
                "video_duration_seconds": float(out.get("duration_seconds", 0.0) or 0.0),
                "title": out.get("title", vid),
                "thumbnail_reference": out.get("thumbnail_url", ""),
                "created_at": out.get("created_at") or _now_iso(),
                "latest_retrieval_timestamp": out.get("retrieved_at") or _now_iso(),
                "snapshot_history": [],
                "latest_metrics": {
                    "views": m.get("views"),
                    "engaged_views": m.get("engagedViews"),
                    "watch_time_minutes": m.get("estimatedMinutesWatched"),
                    "average_view_duration_seconds": m.get("averageViewDuration"),
                    "average_percentage_viewed": m.get("averageViewPercentage"),
                    "impressions": m.get("impressions"),
                    "ctr": m.get("impressionClickThroughRate"),
                    "likes": m.get("likes"),
                    "comments": m.get("comments"),
                    "subscribers_gained": m.get("subscribersGained"),
                    "returning_viewers": m.get("returningViewers"),
                },
                "traffic_sources": out.get("traffic_sources", []),
                "metadata_extras": {"migrated_from": "legacy_analytics_snapshots"},
            }

        out["video_id"] = out.get("video_id") or vid
        out["schema_version"] = CURRENT_SCHEMA_VERSION
        out["revision"] = max(1, int(out.get("revision", 1) or 1))
        out.setdefault("snapshot_history", [])
        out.setdefault("latest_metrics", {})
        out.setdefault("metadata_extras", {})
        normalized[vid] = out

    return normalized, {
        "source_version": source_version,
        "target_version": CURRENT_SCHEMA_VERSION,
        "migrated_records": migrated_count,
        "total_records": len(normalized),
    }


def migrate_schedule_state(raw: Any) -> Dict[str, Any]:
    """Migrates schedule state dict to schema v2 while preserving existing cadence & slots."""
    out = dict(raw) if isinstance(raw, dict) else {}
    out["schema_version"] = CURRENT_SCHEMA_VERSION
    out["revision"] = max(1, int(out.get("revision", 1) or 1))
    out.setdefault("updated_at", _now_iso())
    out.setdefault("history_runs", [])
    out.setdefault("slot_performance", {})
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  MONOTONIC CONFLICT RESOLUTION (NO STALE OVERWRITES)
# ══════════════════════════════════════════════════════════════════════════════

def merge_production_records(
    local_records: Dict[str, Dict[str, Any]],
    incoming_records: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Merges two production databases safely without allowing stale records to overwrite newer state.
    Conflict rule: higher (revision, updated_at) wins, while unioning unique transition history entries.
    """
    loc_norm, _ = migrate_production_records(local_records)
    inc_norm, _ = migrate_production_records(incoming_records)

    merged = dict(loc_norm)
    conflicts_resolved_local_kept = 0
    conflicts_resolved_incoming_won = 0
    added_from_incoming = 0

    for k, inc in inc_norm.items():
        if k not in merged:
            merged[k] = inc
            added_from_incoming += 1
            continue

        loc = merged[k]
        loc_rank = (int(loc.get("revision", 1)), _parse_ts(loc.get("updated_at")))
        inc_rank = (int(inc.get("revision", 1)), _parse_ts(inc.get("updated_at")))

        winner = dict(inc if inc_rank > loc_rank else loc)
        loser = loc if inc_rank > loc_rank else inc
        if inc_rank > loc_rank:
            conflicts_resolved_incoming_won += 1
        elif loc_rank > inc_rank:
            conflicts_resolved_local_kept += 1

        # Union transition histories without duplicates
        seen = {(h.get("from_state"), h.get("to_state"), h.get("timestamp")) for h in winner.get("history", [])}
        combined_hist = list(winner.get("history", []))
        for h in loser.get("history", []):
            sig = (h.get("from_state"), h.get("to_state"), h.get("timestamp"))
            if sig not in seen:
                seen.add(sig)
                combined_hist.append(h)
        combined_hist.sort(key=lambda x: str(x.get("timestamp", "")))
        winner["history"] = combined_hist
        winner["retry_count"] = max(int(loc.get("retry_count", 0)), int(inc.get("retry_count", 0)))
        winner["recovered_count"] = max(int(loc.get("recovered_count", 0)), int(inc.get("recovered_count", 0)))
        merged[k] = winner

    return merged, {
        "total_merged": len(merged),
        "added_from_incoming": added_from_incoming,
        "incoming_won": conflicts_resolved_incoming_won,
        "stale_incoming_rejected": conflicts_resolved_local_kept,
    }


def merge_growth_records(
    local_records: Dict[str, Dict[str, Any]],
    incoming_records: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Merges two HistoricalPerformanceDB dicts cleanly:
    - Preserves immutable snapshot_history across both sources by (checkpoint, observation_period).
    - Upgrades Null/unavailable owner metrics when genuine owner metrics exist, never the reverse.
    """
    loc_norm, _ = migrate_growth_records(local_records)
    inc_norm, _ = migrate_growth_records(incoming_records)

    merged = dict(loc_norm)
    added = 0
    upgraded_snapshots = 0

    for vid, inc in inc_norm.items():
        if vid not in merged:
            merged[vid] = inc
            added += 1
            continue

        loc = dict(merged[vid])
        snaps_by_key: Dict[Tuple[str, str], dict] = {}
        for src_rec in (loc, inc):
            for s in src_rec.get("snapshot_history", []) or []:
                s_key = (
                    str(s.get("checkpoint", "ad_hoc")),
                    str(s.get("observation_period", str(s.get("retrieval_timestamp", ""))[:10])),
                )
                prev = snaps_by_key.get(s_key)
                if prev is None:
                    snaps_by_key[s_key] = dict(s)
                else:
                    prev_owner = bool(prev.get("owner_analytics_available"))
                    cur_owner = bool(s.get("owner_analytics_available"))
                    if (cur_owner and not prev_owner) or (
                        cur_owner == prev_owner and _parse_ts(s.get("retrieval_timestamp")) > _parse_ts(prev.get("retrieval_timestamp"))
                    ):
                        snaps_by_key[s_key] = dict(s)
                        upgraded_snapshots += 1

        combined_snaps = sorted(snaps_by_key.values(), key=lambda x: str(x.get("retrieval_timestamp", "")))
        loc["snapshot_history"] = combined_snaps
        if _parse_ts(inc.get("latest_retrieval_timestamp")) > _parse_ts(loc.get("latest_retrieval_timestamp")):
            if inc.get("owner_analytics_available") or not loc.get("owner_analytics_available"):
                loc["latest_metrics"] = inc.get("latest_metrics", loc.get("latest_metrics"))
                loc["latest_retrieval_timestamp"] = inc.get("latest_retrieval_timestamp")
                loc["owner_analytics_available"] = bool(inc.get("owner_analytics_available"))
        loc["revision"] = max(int(loc.get("revision", 1)), int(inc.get("revision", 1))) + (1 if upgraded_snapshots else 0)
        loc["schema_version"] = CURRENT_SCHEMA_VERSION
        merged[vid] = loc

    return merged, {
        "total_merged": len(merged),
        "added_from_incoming": added,
        "upgraded_snapshots": upgraded_snapshots,
    }


def merge_schedule_states(local_state: Dict[str, Any], incoming_state: Dict[str, Any]) -> Dict[str, Any]:
    """Merges schedule states monotonically without losing slot publication flags or run history."""
    loc = migrate_schedule_state(local_state)
    inc = migrate_schedule_state(incoming_state)
    loc_rank = (int(loc.get("revision", 1)), _parse_ts(loc.get("updated_at")))
    inc_rank = (int(inc.get("revision", 1)), _parse_ts(inc.get("updated_at")))

    base = dict(inc if inc_rank > loc_rank else loc)
    other = loc if inc_rank > loc_rank else inc

    # Union published slot flags (truthy publication flags monotonically persist)
    for k, v in other.items():
        if k.startswith("last_short_pub_") or k.startswith("last_longform_pub_"):
            if v and not base.get(k):
                base[k] = v

    # Deduplicate history_runs by (type, date_ist, title, url)
    seen = {(r.get("type"), r.get("date_ist"), r.get("url")) for r in base.get("history_runs", [])}
    merged_runs = list(base.get("history_runs", []))
    for r in other.get("history_runs", []):
        sig = (r.get("type"), r.get("date_ist"), r.get("url"))
        if sig not in seen:
            seen.add(sig)
            merged_runs.append(r)
    base["history_runs"] = merged_runs[-200:]
    base["revision"] = max(int(loc.get("revision", 1)), int(inc.get("revision", 1))) + 1
    base["updated_at"] = _now_iso()
    base["schema_version"] = CURRENT_SCHEMA_VERSION
    return base


# ══════════════════════════════════════════════════════════════════════════════
#  SQLITE WAL LEDGER + BACKUP / RESTORE
# ══════════════════════════════════════════════════════════════════════════════

def _connect_sqlite(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS state_blobs (
            store_name TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            revision INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS state_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at TEXT NOT NULL,
            action TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
    """)
    return conn


def sync_to_sqlite(base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Mirrors authoritative JSON stores into local ACID SQLite WAL ledger (`yaas_state.sqlite`)."""
    out_dir = base_dir or getattr(config, "OUTPUT_DIR", "output")
    sqlite_path = os.path.join(out_dir, "yaas_state.sqlite")
    manifest_path = os.path.join(out_dir, "state_manifest.json")
    now = _now_iso()
    synced_stores: Dict[str, Any] = {}

    with CrossProcessFileLock(f"{sqlite_path}.lock"):
        conn = _connect_sqlite(sqlite_path)
        try:
            for fname in STATE_FILES:
                fpath = os.path.join(out_dir, fname)
                if not os.path.exists(fpath):
                    continue
                with CrossProcessFileLock(f"{fpath}.lock"):
                    with open(fpath, encoding="utf-8") as f:
                        raw = json.load(f)
                payload_txt = json.dumps(raw, indent=2, ensure_ascii=False)
                digest = hashlib.sha256(payload_txt.encode("utf-8")).hexdigest()
                rev = int(raw.get("revision", 1)) if isinstance(raw, dict) else 1
                if isinstance(raw, dict) and fname == "production_database.json":
                    rev = sum(int(r.get("revision", 1)) for r in raw.values() if isinstance(r, dict)) or 1
                conn.execute(
                    """
                    INSERT INTO state_blobs (store_name, schema_version, revision, updated_at, sha256, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(store_name) DO UPDATE SET
                        schema_version=excluded.schema_version,
                        revision=excluded.revision,
                        updated_at=excluded.updated_at,
                        sha256=excluded.sha256,
                        payload_json=excluded.payload_json
                    """,
                    (fname, CURRENT_SCHEMA_VERSION, rev, now, digest, payload_txt),
                )
                synced_stores[fname] = {"revision": rev, "sha256": digest}

            conn.execute(
                "INSERT INTO state_sync_log (synced_at, action, details_json) VALUES (?, ?, ?)",
                (now, "sync_to_sqlite", json.dumps(synced_stores)),
            )
            conn.commit()
        finally:
            conn.close()

    manifest = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "last_sync_at": now,
        "authoritative_stores": synced_stores,
        "sqlite_ledger": os.path.basename(sqlite_path),
    }
    _atomic_write_json(manifest_path, manifest)
    return manifest


def restore_from_sqlite(base_dir: Optional[str] = None, store_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Restores authoritative JSON stores from the SQLite WAL ledger."""
    out_dir = base_dir or getattr(config, "OUTPUT_DIR", "output")
    sqlite_path = os.path.join(out_dir, "yaas_state.sqlite")
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"SQLite ledger not found: {sqlite_path}")

    restored = []
    with CrossProcessFileLock(f"{sqlite_path}.lock"):
        conn = _connect_sqlite(sqlite_path)
        try:
            rows = conn.execute("SELECT store_name, sha256, payload_json FROM state_blobs").fetchall()
        finally:
            conn.close()

    targets = set(store_names) if store_names else set(STATE_FILES)
    for store_name, expected_sha, payload_json in rows:
        if store_name not in targets:
            continue
        actual_sha = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(f"Checksum mismatch restoring '{store_name}' from SQLite ledger.")
        data = json.loads(payload_json)
        _atomic_write_json(os.path.join(out_dir, store_name), data)
        restored.append(store_name)
    return {"restored": restored, "restored_at": _now_iso()}


def create_state_backup(base_dir: Optional[str] = None, label: str = "auto", keep_last: int = 10) -> Dict[str, Any]:
    """Creates a checksummed snapshot backup of all authoritative state JSON files in `<base_dir>/backups/`."""
    out_dir = base_dir or getattr(config, "OUTPUT_DIR", "output")
    backups_root = os.path.join(out_dir, "backups")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    b_dir = os.path.join(backups_root, f"{label}_{stamp}_{uuid.uuid4().hex[:4]}")
    os.makedirs(b_dir, exist_ok=True)

    checksums: Dict[str, str] = {}
    backed_files: List[str] = []
    for fname in STATE_FILES:
        src = os.path.join(out_dir, fname)
        if os.path.exists(src):
            dst = os.path.join(b_dir, fname)
            shutil.copy2(src, dst)
            checksums[fname] = _sha256_file(dst)
            backed_files.append(fname)

    pending_src = os.path.join(out_dir, "pending_uploads")
    if os.path.isdir(pending_src):
        p_files = [f for f in os.listdir(pending_src) if f.endswith(".json")]
        if p_files:
            p_dst = os.path.join(b_dir, "pending_uploads")
            os.makedirs(p_dst, exist_ok=True)
            for pf in p_files:
                shutil.copy2(os.path.join(pending_src, pf), os.path.join(p_dst, pf))
                checksums[f"pending_uploads/{pf}"] = _sha256_file(os.path.join(p_dst, pf))
                backed_files.append(f"pending_uploads/{pf}")

    meta = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "label": label,
        "created_at": _now_iso(),
        "files": backed_files,
        "checksums": checksums,
    }
    _atomic_write_json(os.path.join(b_dir, "backup_manifest.json"), meta)

    # Prune oldest backups beyond keep_last
    if keep_last > 0 and os.path.isdir(backups_root):
        all_b = sorted(
            [os.path.join(backups_root, d) for d in os.listdir(backups_root) if os.path.isdir(os.path.join(backups_root, d))],
            key=lambda p: os.path.getmtime(p),
        )
        for old_b in all_b[:-keep_last]:
            shutil.rmtree(old_b, ignore_errors=True)

    return {"backup_dir": b_dir, **meta}


def restore_state_backup(backup_dir: str, base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Verifies SHA-256 checksums and atomically restores state files from a backup snapshot."""
    out_dir = base_dir or getattr(config, "OUTPUT_DIR", "output")
    manifest_path = os.path.join(backup_dir, "backup_manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Backup manifest missing in {backup_dir}")

    manifest = json.load(open(manifest_path, encoding="utf-8"))
    checksums = manifest.get("checksums", {})
    restored: List[str] = []

    for rel_path, expected_sha in checksums.items():
        src = os.path.join(backup_dir, rel_path)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Backup file missing: {src}")
        if _sha256_file(src) != expected_sha:
            raise ValueError(f"Checksum verification failed for {rel_path}")

    for rel_path in checksums:
        src = os.path.join(backup_dir, rel_path)
        dst = os.path.join(out_dir, rel_path)
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(rel_path)

    return {"restored": restored, "restored_from": backup_dir, "restored_at": _now_iso()}


def generate_persistent_state_health_report(base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Generates Phase 23 Persistent Production-State Health Report."""
    out_dir = base_dir or getattr(config, "OUTPUT_DIR", "output")
    os.makedirs(out_dir, exist_ok=True)
    sync_meta = sync_to_sqlite(base_dir=out_dir)

    stores_status: Dict[str, Any] = {}
    for fname in STATE_FILES:
        fpath = os.path.join(out_dir, fname)
        if not os.path.exists(fpath):
            stores_status[fname] = {"exists": False, "valid_json": False, "record_count": 0, "schema_version": None}
            continue
        try:
            raw = json.load(open(fpath, encoding="utf-8"))
            if fname == "production_database.json":
                norm, info = migrate_production_records(raw)
                stores_status[fname] = {
                    "exists": True,
                    "valid_json": True,
                    "record_count": len(norm),
                    "schema_version": CURRENT_SCHEMA_VERSION if norm else info.get("source_version"),
                }
            elif fname == "historical_performance_db.json":
                norm, info = migrate_growth_records(raw)
                stores_status[fname] = {
                    "exists": True,
                    "valid_json": True,
                    "record_count": len(norm),
                    "schema_version": CURRENT_SCHEMA_VERSION if norm else info.get("source_version"),
                }
            elif isinstance(raw, list):
                stores_status[fname] = {"exists": True, "valid_json": True, "record_count": len(raw), "schema_version": CURRENT_SCHEMA_VERSION}
            else:
                stores_status[fname] = {
                    "exists": True,
                    "valid_json": True,
                    "record_count": len(raw.get("history_runs", [])) if "history_runs" in raw else len(raw),
                    "schema_version": raw.get("schema_version", 1),
                    "revision": raw.get("revision", 1),
                }
        except Exception as e:
            stores_status[fname] = {"exists": True, "valid_json": False, "error": str(e)}

    backups_root = os.path.join(out_dir, "backups")
    backup_dirs = (
        sorted(d for d in os.listdir(backups_root) if os.path.isdir(os.path.join(backups_root, d)))
        if os.path.isdir(backups_root)
        else []
    )

    report = {
        "generated_at": _now_iso(),
        "data_provenance": "verified_live_state",
        "authoritative_strategy": "git_tracked_authoritative_json_plus_sqlite_wal_ledger",
        "cache_only_storage_rejected": True,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "stores": stores_status,
        "sqlite_ledger": {
            "path": os.path.join(out_dir, "yaas_state.sqlite"),
            "exists": os.path.exists(os.path.join(out_dir, "yaas_state.sqlite")),
            "synced_stores": list(sync_meta.get("authoritative_stores", {}).keys()),
        },
        "backups_available": len(backup_dirs),
        "latest_backup": backup_dirs[-1] if backup_dirs else None,
    }
    report_path = os.path.join(out_dir, "persistent_state_health_report.json")
    _atomic_write_json(report_path, report)
    report["report_path"] = report_path
    return report


def load_git_ref_json(git_ref: str, repo_rel_path: str) -> Optional[Dict[str, Any]]:
    """Read-only helper that loads a JSON blob from a git ref without touching working tree or branches."""
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "show", f"{git_ref}:{repo_rel_path}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        data = json.loads(proc.stdout)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def reconcile_branch_schedule_state(
    output_dir: Optional[str] = None,
    git_ref: str = "origin/main",
    incoming_schedule: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Safely merges CI-committed schedule state (e.g. from origin/main:output/automation_schedule.json)
    into the local automation_schedule.json using monotonic merge_schedule_states().
    Never merges code or overwrites newer local records.
    """
    out_dir = output_dir or getattr(config, "OUTPUT_DIR", "output")
    sched_path = os.path.join(out_dir, "automation_schedule.json")
    local_sched: Dict[str, Any] = {}
    if os.path.exists(sched_path):
        try:
            with open(sched_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    local_sched = loaded
        except Exception:
            local_sched = {}
    incoming = incoming_schedule if incoming_schedule is not None else load_git_ref_json(git_ref, "output/automation_schedule.json")
    if not isinstance(incoming, dict) or not incoming:
        return {
            "merged": False,
            "reason": "no_incoming_schedule",
            "git_ref": git_ref,
            "local_history_runs": len(local_sched.get("history_runs", []) or []),
            "merged_history_runs": len(local_sched.get("history_runs", []) or []),
            "new_url_keys_added": 0,
        }

    local_urls_before = {k for k in local_sched if k.endswith("_url")}
    merged = merge_schedule_states(local_sched, incoming)
    merged_urls_after = {k for k in merged if k.endswith("_url")}
    new_urls = sorted(merged_urls_after - local_urls_before)

    _atomic_write_json(sched_path, merged)
    sync_to_sqlite(out_dir)

    return {
        "merged": True,
        "git_ref": git_ref,
        "local_history_runs": len(local_sched.get("history_runs", []) or []),
        "incoming_history_runs": len(incoming.get("history_runs", []) or []),
        "merged_history_runs": len(merged.get("history_runs", []) or []),
        "new_url_keys_added": len(new_urls),
    }
