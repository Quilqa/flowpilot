"""Configuration and project path helpers for FlowPilot."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Project root = parent of the backend package directory.
ROOT = Path(__file__).resolve().parent.parent

FLOWS_DIR = ROOT / "flows"
TEMPLATES_DIR = ROOT / "templates"
LOGS_DIR = ROOT / "logs"
CONFIG_PATH = ROOT / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "port": 8321,
    "default_confidence": 0.85,
    "default_poll_interval_ms": 250,
    "default_poll_timeout_ms": 5000,
    "start_delay_ms": 3000,
    "max_duration_ms": 1800000,
    "loop_guard_iterations": 10000,
    "failsafe": True,
    "panic_hotkey": "ctrl+alt+esc",
}


def ensure_dirs() -> None:
    """Create the standard project folders if they do not exist."""
    for d in (FLOWS_DIR, TEMPLATES_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load config.json, filling in any missing keys with defaults."""
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def flow_path(name: str) -> Path:
    """Resolve a flow name to its JSON path, guarding against traversal."""
    safe = _safe_name(name)
    return FLOWS_DIR / f"{safe}.json"


def template_dir_for(flow_name: str) -> Path:
    d = TEMPLATES_DIR / _safe_name(flow_name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    """Strip path separators / traversal from a user-supplied name."""
    name = name.strip().replace("\\", "/").split("/")[-1]
    if name.endswith(".json"):
        name = name[: -len(".json")]
    # Keep it filesystem-friendly.
    cleaned = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip()
    return cleaned or "untitled"
