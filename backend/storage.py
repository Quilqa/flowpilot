"""Flow persistence: load/save/list/duplicate/rename/delete JSON flows."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from . import config
from .models import Flow


def list_flows() -> list[dict[str, Any]]:
    """Return summary metadata for every flow in flows/."""
    config.ensure_dirs()
    out: list[dict[str, Any]] = []
    for p in sorted(config.FLOWS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append(
            {
                "name": data.get("name", p.stem),
                "file": p.name,
                "nodes": len(data.get("nodes", [])),
                "inputs": data.get("inputs", []),
                "modified": p.stat().st_mtime,
            }
        )
    return out


def load_flow(name: str) -> Flow:
    p = config.flow_path(name)
    if not p.exists():
        raise FileNotFoundError(f"Flow '{name}' not found")
    data = json.loads(p.read_text(encoding="utf-8"))
    return Flow.model_validate(data)


def save_flow(flow: Flow) -> Path:
    config.ensure_dirs()
    p = config.flow_path(flow.name)
    p.write_text(json.dumps(flow.to_json_dict(), indent=2), encoding="utf-8")
    return p


def delete_flow(name: str) -> None:
    p = config.flow_path(name)
    if p.exists():
        p.unlink()
    tdir = config.TEMPLATES_DIR / config._safe_name(name)
    if tdir.exists():
        shutil.rmtree(tdir, ignore_errors=True)


def _rewrite_template_paths(flow: Flow, old_safe: str, new_safe: str) -> None:
    """Repoint node template params from templates/<old>/ to templates/<new>/.

    Templates live in a per-flow folder, so renaming/duplicating a flow must
    also update the paths stored inside Image Condition nodes, or they break.
    """
    if old_safe == new_safe:
        return
    old_prefix = f"templates/{old_safe}/"
    new_prefix = f"templates/{new_safe}/"
    for node in flow.nodes:
        tpl = node.params.get("template")
        if isinstance(tpl, str) and tpl.startswith(old_prefix):
            node.params["template"] = new_prefix + tpl[len(old_prefix):]


def rename_flow(old: str, new: str) -> Flow:
    flow = load_flow(old)
    old_path = config.flow_path(old)
    old_safe = config._safe_name(old)
    new_safe = config._safe_name(new)
    old_tdir = config.TEMPLATES_DIR / old_safe

    flow.name = new_safe
    _rewrite_template_paths(flow, old_safe, new_safe)
    save_flow(flow)

    new_tdir = config.TEMPLATES_DIR / new_safe
    if old_tdir.exists() and old_tdir != new_tdir:
        if new_tdir.exists():
            shutil.rmtree(new_tdir, ignore_errors=True)
        shutil.move(str(old_tdir), str(new_tdir))

    if config.flow_path(old) != config.flow_path(flow.name) and old_path.exists():
        old_path.unlink()
    return flow


def duplicate_flow(name: str, new_name: str | None = None) -> Flow:
    flow = load_flow(name)
    old_safe = config._safe_name(name)
    base = new_name or f"{flow.name} copy"
    flow.name = _unique_name(base)
    new_safe = config._safe_name(flow.name)

    # Copy templates into the new flow's folder, then repoint node paths at it
    # so the duplicate is independent of the original (which may be deleted).
    src = config.TEMPLATES_DIR / old_safe
    dst = config.TEMPLATES_DIR / new_safe
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    _rewrite_template_paths(flow, old_safe, new_safe)
    save_flow(flow)
    return flow


def _unique_name(base: str) -> str:
    base = config._safe_name(base)
    candidate = base
    i = 2
    while config.flow_path(candidate).exists():
        candidate = f"{base} {i}"
        i += 1
    return candidate
