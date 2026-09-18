"""Append only this MCP entry, preserving all existing Codex settings."""
import os
import json
import shutil
import tomllib
from datetime import datetime
from pathlib import Path

base = Path(__file__).resolve().parent
target = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
original = target.read_bytes() if target.exists() else b""
settings = tomllib.loads(original.decode("utf-8"))
python = base / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.is_file():
    raise SystemExit("Create .venv and install the project dependencies first.")
entry = "\n".join([
    "[mcp_servers.pterodactyl]",
    "command = " + json.dumps(str(python)),
    "args = [" + json.dumps(str(base / "pterodactyl_mcp.py")) + "]",
    "startup_timeout_sec = 20",
    "tool_timeout_sec = 180",
    "",
])
expected = tomllib.loads(entry)["mcp_servers"]["pterodactyl"]
existing = settings.get("mcp_servers", {}).get("pterodactyl")
if existing is not None:
    if existing != expected:
        raise SystemExit("A different pterodactyl MCP already exists; no settings changed.")
    print("Pterodactyl MCP already registered.")
else:
    updated = original + b"\n\n" + entry.encode("utf-8")
    tomllib.loads(updated.decode("utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if target.exists():
        backup = target.with_name("config.toml.before-pterodactyl-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(target, backup)
    if (target.read_bytes() if target.exists() else b"") != original:
        raise SystemExit("Codex settings changed concurrently; no settings changed.")
    target.write_bytes(updated)
    actual = tomllib.loads(target.read_text(encoding="utf-8"))
    assert actual["mcp_servers"]["pterodactyl"] == expected
    del actual["mcp_servers"]["pterodactyl"]
    settings.setdefault("mcp_servers", {})
    assert actual == settings, "Unexpected settings change"
    print("Registered:", target)
    if backup:
        print("Backup:", backup)
