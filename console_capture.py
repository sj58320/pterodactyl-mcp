"""Bounded Wings capture, with an optional caller action after authentication."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

MAX_BYTES = 32 * 1024 * 1024  # Combined raw events and readable output.
# A watched capture ends early, so it may wait longer; stay below the MCP client's 180 s tool timeout.
WATCH_SECONDS = 150
ENDED = {"duration_elapsed", "until_matched", "fail_on_matched"}
MAX_LINES = 100_000
MAX_GROUPS = 5000
OUTPUT_EVENTS = {"console output", "daemon message", "install output"}
AUTH_ERRORS = {"jwt error", "token expired", "error"}
ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
SUSPECT = re.compile(r"\b(error|exception|fatal|failed|failure|panic|segfault|warning|warn)\b|오류|경고", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(line: str) -> str:
    return CONTROL.sub("", ANSI.sub("", line)).rstrip("\r\n")


def preview(number: int, line: str) -> dict:
    text = clean(line)
    return {"line": number, "text": text[:500], "text_truncated": len(text) > 500}


def summarize(path: Path) -> dict:
    groups = {}
    previous = deque(maxlen=2)
    candidates = []
    candidate_count = ungrouped = total = 0
    with path.open(encoding="utf-8", newline="") as source:
        for total, raw in enumerate(source, 1):
            line = clean(raw)
            item = preview(total, raw)
            for sample in candidates:
                if sample["line"] < total <= sample["line"] + 2:
                    sample["context"].append(item)
            if SUSPECT.search(line):
                candidate_count += 1
                if len(candidates) < 10:
                    candidates.append({"line": total, "context": [*previous, item]})
            previous.append(item)
            key = hashlib.sha256(line.encode("utf-8")).digest()
            if key in groups:
                groups[key]["count"] += 1
            elif len(groups) < MAX_GROUPS:
                groups[key] = {"text": line[:500], "text_truncated": len(line) > 500, "count": 1, "first_line": total}
            else:
                ungrouped += 1
    repeated = sorted((g for g in groups.values() if g["count"] > 1), key=lambda g: -g["count"])[:10]
    return {"lines": total, "repeated_messages": repeated, "error_warning_candidates": candidate_count,
            "candidate_context": candidates, "ungrouped_lines": ungrouped,
            "note": "Keyword matches are candidates, not confirmed faults. Repetition counts use exact text after ANSI removal; timestamps are not normalized."}


def capture_path(root: Path, capture_id: str) -> Path:
    if not re.fullmatch(r"\d{8}T\d{6}Z-[a-f0-9]{12}", capture_id):
        raise ValueError("Invalid capture_id; use the ID returned by capture_console.")
    root = root.resolve()
    path = (root / capture_id).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Capture must stay inside the captures directory.")
    return path


def read_capture(root: Path, capture_id: str, start_line: int, limit: int, contains: str) -> dict:
    if not 1 <= start_line or not 1 <= limit <= 100 or len(contains) > 500:
        raise ValueError("Use start_line >= 1, limit 1..100, and a search string up to 500 characters.")
    path = capture_path(root, capture_id) / "console.log"
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Capture log does not exist inside the captures directory.")
    result = []
    next_line = None
    with path.open(encoding="utf-8", newline="") as source:
        for number, raw in enumerate(source, 1):
            if number < start_line or contains.casefold() not in clean(raw).casefold():
                continue
            if len(result) == limit:
                next_line = number
                break
            result.append(preview(number, raw))
    return {"capture_id": capture_id, "lines": result, "next_line": next_line,
            "note": "ANSI removed and each displayed line limited to 500 characters. Original text remains in the capture files."}


def parse_message(raw) -> tuple[str, list[str]]:
    message = json.loads(raw)
    if not isinstance(message, dict) or not isinstance(message.get("event"), str):
        raise ValueError("Invalid WebSocket event.")
    args = message.get("args") or []
    if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
        raise ValueError("Invalid WebSocket event arguments.")
    return message["event"], args


def watch_pattern(name: str, value):
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 500:
        raise ValueError(f"{name} must be a regular expression of 1..500 characters.")
    try:
        return re.compile(value)
    except re.error as exc:
        raise ValueError(f"{name} is not a valid regular expression: {exc}") from None


def check_watch(seconds, until: str | None, fail_on: str | None):
    """Validate a capture duration and optional stop patterns before any connection is made."""
    until_re, fail_re = watch_pattern("until", until), watch_pattern("fail_on", fail_on)
    limit = WATCH_SECONDS if until_re or fail_re else 60
    if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= limit:
        raise ValueError(f"seconds must be an integer between 1 and {limit}" + ("." if limit == WATCH_SECONDS else " (up to 150 with until/fail_on)."))
    return until_re, fail_re


async def capture(root: Path, server: str, credentials: dict, origin: str, seconds: int, include_recent: bool, on_ready=None,
                  until: str | None = None, fail_on: str | None = None) -> dict:
    """Record console output for `seconds`. With `until`/`fail_on`, stop at the first ANSI-stripped line matching either
    (fail_on wins on the same line); `seconds` is then the maximum wait, up to WATCH_SECONDS."""
    until_re, fail_re = check_watch(seconds, until, fail_on)
    socket, token = credentials.get("socket", ""), credentials.get("token", "")
    parsed = urlsplit(socket)
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or not token:
        raise ValueError("Invalid WebSocket credentials returned by the panel.")
    # Independent logger: DEBUG frame logs can contain authentication tokens.
    logger = logging.Logger("pterodactyl.console", level=logging.CRITICAL)
    folder = None
    metadata = {}
    started = None
    cancelled = False
    try:
        async with connect(socket, origin=origin, proxy=None, open_timeout=10, close_timeout=2,
                           max_size=2 * 1024 * 1024, max_queue=32, logger=logger) as ws:
            await ws.send(json.dumps({"event": "auth", "args": [token]}))
            async with asyncio.timeout(10):
                while True:
                    event, args = parse_message(await ws.recv())
                    if event == "auth success":
                        break
                    if event in AUTH_ERRORS:
                        raise ValueError("WebSocket authentication rejected; check websocket.connect permission.")
            capture_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
            candidate = capture_path(root, capture_id)
            candidate.mkdir(parents=True, exist_ok=False)
            folder = candidate
            started = time.monotonic()
            metadata = {"capture_id": capture_id, "server": server, "started_at": utc_now(), "requested_seconds": seconds,
                        "include_recent": include_recent, "scope": "recent_and_live_mixed" if include_recent else "live_after_connect",
                        "events": 0, "saved_bytes": 0, "status": "capturing", "stop_reason": None,
                        "timestamp_meaning": "Local UTC receipt time, not the original server event time.",
                        "raw_events_path": str(folder / "events.jsonl"), "log_path": str(folder / "console.log")}
            if until_re or fail_re:
                metadata.update(until=until, fail_on=fail_on, match=None)
            (folder / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            started = time.monotonic()
            deadline = started + seconds
            line_count = 0
            with (folder / "events.jsonl").open("xb") as raw_file, (folder / "console.log").open("xb") as log_file:
                if include_recent:
                    await ws.send(json.dumps({"event": "send logs", "args": []}))
                if on_ready is not None:
                    metadata["command_result"] = {"accepted": None, "dispatch_attempted": True}
                    metadata["command_result"] = await on_ready()
                    if metadata["command_result"].get("accepted") is False:
                        metadata["stop_reason"] = "command_rejected"
                    # Allow the requested observation time after the API response.
                    deadline = time.monotonic() + seconds
                while metadata["stop_reason"] is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        metadata["stop_reason"] = "duration_elapsed"
                        break
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    except TimeoutError:
                        metadata["stop_reason"] = "duration_elapsed"
                        break
                    event, args = parse_message(raw)
                    if event in AUTH_ERRORS:
                        metadata["stop_reason"] = "authentication_expired_or_server_error"
                        break
                    if event not in OUTPUT_EVENTS:
                        continue
                    record = (json.dumps({"received_at": utc_now(), "event": event, "args": args}, ensure_ascii=False) + "\n").encode("utf-8")
                    # JSONL is the exact received text payload. The readable file separates arguments with newlines.
                    content = "".join(a if a.endswith("\n") else a + "\n" for a in args).encode("utf-8")
                    new_lines = content.count(b"\n")
                    size = len(record) + len(content)
                    if metadata["saved_bytes"] + size > MAX_BYTES or line_count + new_lines > MAX_LINES:
                        metadata["stop_reason"] = "capture_limit_reached"
                        break
                    raw_file.write(record)
                    log_file.write(content)
                    if until_re or fail_re:
                        for offset, line in enumerate(content.decode("utf-8").split("\n")[:-1], start=line_count + 1):
                            text = clean(line)
                            kind = "fail_on" if fail_re and fail_re.search(text) else "until" if until_re and until_re.search(text) else None
                            if kind:
                                metadata["match"] = {"kind": kind, "line": offset, "text": text[:500]}
                                metadata["stop_reason"] = kind + "_matched"
                                break
                    line_count += new_lines
                    metadata["events"] += 1
                    metadata["saved_bytes"] += size
                    # Yield even when recv() drains an already-full queue; allow cancellation during floods.
                    await asyncio.sleep(0)
    except asyncio.CancelledError:
        if folder is not None:
            metadata["stop_reason"] = "cancelled"
        cancelled = True
        raise
    except (WebSocketException, OSError, TimeoutError, ValueError):
        if folder is None:
            raise ValueError("Console connection/authentication failed. Check panel/Wings reachability and websocket.connect permission.") from None
        metadata["stop_reason"] = "connection_protocol_or_storage_error"
    finally:
        if folder is not None:
            metadata["elapsed_seconds"] = round(time.monotonic() - started, 3)
            metadata["finished_at"] = utc_now()
            metadata["status"] = "completed" if metadata["stop_reason"] in ENDED else "partial"
            try:
                # Files are closed above, including on cancellation. A hard process kill may still leave status=capturing.
                if (folder / "console.log").exists():
                    metadata["summary"] = summarize(folder / "console.log")
                (folder / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            except (OSError, UnicodeError):
                if not cancelled:
                    raise ValueError(f"Could not finish saving the console capture. Partial data may exist at {folder}.") from None
    return metadata
