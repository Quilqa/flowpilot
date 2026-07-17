"""Manages a single active flow run and fans out its events to listeners.

FlowPilot runs one flow at a time (it drives the real mouse/keyboard), so a
process-wide singleton is the right model.
"""
from __future__ import annotations

import json
import queue
import threading
from datetime import datetime
from typing import Any, Optional

from . import config
from .engine import FlowRunner, RunResult
from .models import Flow


class RunManager:
    def __init__(self) -> None:
        self._runner: Optional[FlowRunner] = None
        self._thread: Optional[threading.Thread] = None
        self._listeners: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._result: Optional[RunResult] = None
        self._log_path: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def add_listener(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._listeners.append(q)
        return q

    def remove_listener(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._listeners:
                self._listeners.remove(q)

    def _broadcast(self, event: dict[str, Any]) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for q in listeners:
            q.put(event)

    def start(self, flow: Flow, variables: dict[str, str] | None = None) -> bool:
        if self.is_running:
            return False
        self._result = None

        # Persist every run to logs/ (one file per run, matching runner.py), so
        # UI runs are recorded too — not just the CLI. Failure to open the log
        # must not block the run, so guard it.
        config.ensure_dirs()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = config.LOGS_DIR / f"{config._safe_name(flow.name)}_{stamp}.log"
        try:
            log_file = open(log_path, "w", encoding="utf-8")
            self._log_path = str(log_path)
        except OSError:
            log_file = None
            self._log_path = None

        def on_event(event: dict[str, Any]) -> None:
            if log_file is not None:
                try:
                    ts = datetime.now().isoformat(timespec="milliseconds")
                    log_file.write(f"[{ts}] {json.dumps(event, default=str)}\n")
                    log_file.flush()
                except (ValueError, OSError):
                    pass
            self._broadcast(event)

        self._runner = FlowRunner(flow, variables=variables, on_event=on_event)

        def _run() -> None:
            try:
                self._result = self._runner.run()
            finally:
                if log_file is not None:
                    try:
                        log_file.close()
                    except OSError:
                        pass
                self._broadcast({"type": "run_finished", "log": self._log_path})

        self._thread = threading.Thread(target=_run, daemon=True, name="flow-run")
        self._thread.start()
        return True

    def stop(self) -> None:
        if self._runner:
            self._runner.stop()

    def pause(self) -> None:
        if self._runner:
            self._runner.pause()
            self._broadcast({"type": "paused"})

    def resume(self) -> None:
        if self._runner:
            self._runner.resume()
            self._broadcast({"type": "resumed"})

    @property
    def result(self) -> Optional[RunResult]:
        return self._result


# Process-wide singleton.
manager = RunManager()
