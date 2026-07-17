#!/usr/bin/env python
"""FlowPilot web UI server entry point.

    python server.py

Serves the React UI and executes flows. Registers the global panic hotkey.
"""
from __future__ import annotations

import sys

import uvicorn

from backend import capture, config
from backend.panic import register as register_panic
from backend.runmanager import manager
from backend.server import app


def main() -> int:
    capture.set_dpi_awareness()  # once, before any capture/mouse movement
    cfg = config.load_config()
    port = int(cfg.get("port", 8321))

    if register_panic(cfg.get("panic_hotkey", "ctrl+alt+esc"), manager.stop):
        print(f"[FlowPilot] Panic hotkey registered: {cfg.get('panic_hotkey')}")
    else:
        print("[FlowPilot] Warning: could not register panic hotkey")

    dist = config.ROOT / "frontend" / "dist"
    if not dist.exists():
        print("[FlowPilot] Frontend not built yet. Run:  cd frontend && npm install && npm run build")
    print(f"[FlowPilot] Serving on http://localhost:{port}")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
