"""Local capture and file-backup indexes; never reads outside their configured roots."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

RECORD_ID = re.compile(r"\d{8}T\d{6}Z-[a-f0-9]{12}")
SERVER_ID = re.compile(r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})?")


def same_server(left: str, right: str) -> bool:
    if not SERVER_ID.fullmatch(left) or not SERVER_ID.fullmatch(right):
        return False
    return left.lower() == right.lower() if len(left) == len(right) else left[:8].lower() == right[:8].lower()


def within(root: Path, path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Record path escapes its configured directory.")
    return path


def read_metadata(root: Path, folder: Path) -> dict:
    path = within(root, folder / "metadata.json")
    with path.open("rb") as source:
        raw = source.read(128 * 1024 + 1)
    if len(raw) > 128 * 1024:
        raise ValueError("Record metadata is too large.")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Invalid record metadata.")
    return data


def parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Date must be an ISO-8601 string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            if len(value) != 10:
                raise ValueError()
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise ValueError("Use an ISO-8601 timestamp with timezone, or YYYY-MM-DD (UTC).") from None


def page(rows: list[dict], offset: int, limit: int, skipped: int) -> dict:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("Use offset >= 0 and limit 1..100.")
    return {"items": rows[offset:offset + limit], "total": len(rows),
            "next_offset": offset + limit if offset + limit < len(rows) else None, "skipped_invalid": skipped}


def list_captures(root: Path, server: str | None, since: str | None, until: str | None, offset: int, limit: int) -> dict:
    lower, upper = parse_date(since), parse_date(until)
    if lower and upper and lower >= upper:
        raise ValueError("since must be earlier than until (exclusive).")
    rows, skipped = [], 0
    for folder in root.iterdir() if root.exists() else []:
        if not RECORD_ID.fullmatch(folder.name):
            continue
        try:
            data = read_metadata(root, folder)
            if data.get("capture_id") != folder.name or not isinstance(data.get("server"), str) or not SERVER_ID.fullmatch(data["server"]):
                raise ValueError("Invalid capture metadata.")
            when = parse_date(data["started_at"])
            if when is None:
                raise ValueError("Missing capture timestamp.")
            if server and not same_server(server, data["server"]):
                continue
            if lower and when < lower or upper and when >= upper:
                continue
            row = {k: data.get(k) for k in ("capture_id", "server", "started_at", "finished_at", "status", "stop_reason", "scope", "events", "saved_bytes")}
            row["lines"] = data.get("summary", {}).get("lines")
            rows.append(row)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            skipped += 1
    rows.sort(key=lambda r: (parse_date(r["started_at"]), r["capture_id"]), reverse=True)
    return page(rows, offset, limit, skipped)


def backup_metadata(root: Path, backup_id: str) -> tuple[Path, dict]:
    parts = backup_id.split("/")
    if len(parts) != 2 or not SERVER_ID.fullmatch(parts[0]) or not RECORD_ID.fullmatch(parts[1]):
        raise ValueError("Use a backup_id returned by list_file_backups.")
    folder = within(root, root / parts[0] / parts[1])
    data = read_metadata(root, folder)
    if data.get("server") != parts[0] or not isinstance(data.get("path"), str) or not re.fullmatch(r"[a-f0-9]{64}", data.get("sha256", "")):
        raise ValueError("Invalid backup metadata.")
    return folder, data


def list_backups(root: Path, server: str | None, path: str | None, offset: int, limit: int) -> dict:
    rows, skipped = [], 0
    for server_dir in root.iterdir() if root.exists() else []:
        if not SERVER_ID.fullmatch(server_dir.name) or server and not same_server(server_dir.name, server):
            continue
        try:
            folders = list(within(root, server_dir).iterdir())
        except (OSError, ValueError):
            skipped += 1
            continue
        for folder in folders:
            if not RECORD_ID.fullmatch(folder.name):
                continue
            backup_id = server_dir.name + "/" + folder.name
            try:
                folder, data = backup_metadata(root, backup_id)
                original = within(root, folder / "original.bin")
                if path is not None and data["path"] != path:
                    continue
                created_at = data.get("created_at") or datetime.strptime(folder.name[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
                if parse_date(created_at) is None:
                    raise ValueError("Missing backup timestamp.")
                rows.append({"backup_id": backup_id, "server": data["server"], "path": data["path"],
                             "sha256": data["sha256"], "bytes": original.stat().st_size,
                             "created_at": created_at})
            except (OSError, ValueError, TypeError):
                skipped += 1
    rows.sort(key=lambda r: (parse_date(r["created_at"]), r["backup_id"]), reverse=True)
    return page(rows, offset, limit, skipped)


def load_backup(root: Path, backup_id: str, max_bytes: int) -> tuple[dict, bytes]:
    folder, data = backup_metadata(root, backup_id)
    with within(root, folder / "original.bin").open("rb") as source:
        original = source.read(max_bytes + 1)
    if len(original) > max_bytes:
        raise ValueError("Backup exceeds the supported file-edit size.")
    if hashlib.sha256(original).hexdigest() != data["sha256"]:
        raise ValueError("Backup integrity check failed; no server files were changed.")
    return data, original
