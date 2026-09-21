"""Prompt-as-versioned-artifact registry.

Prompts are stored as plain text files under app/prompts/texts/<agent_key>/<version>.md
instead of being hardcoded string literals in agent.py. A manifest.json pins
which version is "current" (served in prod) per agent. Rolling back a bad
prompt change is repointing the manifest via `rollback()` - no code deploy
needed, and every change is appended to history.jsonl for audit.

Version resolution precedence (highest wins):
1. A programmatic override set via `use_version()` (used by evals/ab_test.py
   to run the same process against two versions without restarting).
2. The `PROMPT_VERSION_OVERRIDES` env var, e.g. '{"account_agent": "v2"}'
   (useful for canarying a version in one deployment without touching the
   shared manifest).
3. The manifest's "current" pointer (the actual production default).
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent
_TEXTS_DIR = _PROMPTS_DIR
_MANIFEST_PATH = _PROMPTS_DIR / "manifest.json"
_HISTORY_PATH = _PROMPTS_DIR / "history.jsonl"

_lock = threading.Lock()
_runtime_overrides: dict[str, str] = {}


@dataclass(frozen=True)
class PromptRecord:
    agent_key: str
    version: str
    text: str


def _load_manifest() -> dict:
    with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_manifest(manifest: dict) -> None:
    with open(_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def _env_overrides() -> dict:
    raw = os.getenv("PROMPT_VERSION_OVERRIDES")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def current_version(agent_key: str) -> str:
    if agent_key in _runtime_overrides:
        return _runtime_overrides[agent_key]
    env_overrides = _env_overrides()
    if agent_key in env_overrides:
        return env_overrides[agent_key]
    manifest = _load_manifest()
    try:
        return manifest["current"][agent_key]
    except KeyError as exc:
        raise ValueError(f"No prompt version configured for agent '{agent_key}'") from exc


def use_version(agent_key: str, version: str | None) -> None:
    """Force a specific version for this process only. Pass None to clear.

    Used by A/B test scripts to run the same agent under two prompt versions
    without touching the shared manifest.json that governs prod traffic.
    """
    with _lock:
        if version is None:
            _runtime_overrides.pop(agent_key, None)
        else:
            _runtime_overrides[agent_key] = version


def available_versions(agent_key: str) -> list[str]:
    agent_dir = _TEXTS_DIR / agent_key
    if not agent_dir.exists():
        return []
    return sorted(p.stem for p in agent_dir.glob("*.md"))


def get_prompt(agent_key: str, version: str | None = None) -> PromptRecord:
    resolved_version = version or current_version(agent_key)
    path = _TEXTS_DIR / agent_key / f"{resolved_version}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"No prompt text for agent '{agent_key}' version '{resolved_version}' ({path})"
        )
    text = path.read_text(encoding="utf-8").strip()
    return PromptRecord(agent_key=agent_key, version=resolved_version, text=text)


def promote(agent_key: str, version: str, actor: str = "unknown") -> dict:
    """Point the manifest's "current" version for agent_key at `version`.

    This is the production promotion mechanism. To roll back, call promote()
    again with the previous version, or use rollback() to do that
    automatically from history.jsonl.
    """
    if version not in available_versions(agent_key):
        raise ValueError(
            f"Version '{version}' has no prompt text file for agent '{agent_key}'. "
            f"Available: {available_versions(agent_key)}"
        )
    manifest = _load_manifest()
    manifest.setdefault("current", {})
    previous = manifest["current"].get(agent_key)
    manifest["current"][agent_key] = version
    _save_manifest(manifest)

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent": agent_key,
        "from_version": previous,
        "to_version": version,
        "actor": actor,
    }
    with open(_HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def rollback(agent_key: str, actor: str = "unknown") -> dict:
    """Revert agent_key to the version it had before its most recent promotion."""
    if not _HISTORY_PATH.exists():
        raise RuntimeError("No promotion history to roll back.")
    last_change = None
    with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            if entry["agent"] == agent_key:
                last_change = entry
    if last_change is None or last_change["from_version"] is None:
        raise RuntimeError(f"No prior version recorded for '{agent_key}' to roll back to.")
    return promote(agent_key, last_change["from_version"], actor=f"{actor} (rollback)")


def get_manifest_snapshot() -> dict:
    return _load_manifest()


def get_history(agent_key: str | None = None) -> list[dict]:
    if not _HISTORY_PATH.exists():
        return []
    entries = []
    with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            if agent_key is None or entry["agent"] == agent_key:
                entries.append(entry)
    return entries