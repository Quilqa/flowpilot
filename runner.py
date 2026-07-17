#!/usr/bin/env python
"""FlowPilot headless CLI runner (PRD §7.2).

    python runner.py flows/my_flow.json --var user=john --var count=5 [--log logs/custom.log]

Exit code 0 on success, non-zero on failure/abort (Task Scheduler compatible).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from backend import capture, config
from backend.engine import FlowRunner
from backend.models import Flow
from backend.panic import register as register_panic


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FlowPilot headless flow runner")
    parser.add_argument("flow", help="Path to a flow JSON file (e.g. flows/my_flow.json)")
    parser.add_argument("--var", action="append", default=[], metavar="name=value",
                        help="Set an input variable; repeatable")
    parser.add_argument("--log", default=None, help="Custom log file path")
    parser.add_argument("--no-delay", action="store_true", help="Skip the start-delay countdown")
    return parser.parse_args(argv)


def parse_vars(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Invalid --var '{pair}', expected name=value")
        k, v = pair.split("=", 1)
        out[k.strip()] = v
    return out


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    capture.set_dpi_awareness()  # once, before any capture/mouse movement
    config.ensure_dirs()

    flow_file = Path(args.flow)
    if not flow_file.is_absolute():
        flow_file = config.ROOT / flow_file
    if not flow_file.exists():
        print(f"Flow file not found: {flow_file}", file=sys.stderr)
        return 2

    data = json.loads(flow_file.read_text(encoding="utf-8"))
    flow = Flow.model_validate(data)

    if args.no_delay:
        flow.settings.start_delay_ms = 0

    variables = parse_vars(args.var)

    # Log file: one per run.
    if args.log:
        log_path = Path(args.log)
        if not log_path.is_absolute():
            log_path = config.ROOT / log_path
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = config.LOGS_DIR / f"{flow.name}_{stamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")

    def on_event(evt: dict) -> None:
        line = f"[{datetime.now().isoformat(timespec='milliseconds')}] {json.dumps(evt, default=str)}"
        print(line)
        log_file.write(line + "\n")
        log_file.flush()

    runner = FlowRunner(flow, variables=variables, on_event=on_event)
    register_panic(config.load_config().get("panic_hotkey", "ctrl+alt+esc"), runner.stop)

    try:
        result = runner.run()
    finally:
        log_file.close()

    print(f"Result: success={result.success} exit_code={result.exit_code} - {result.message}")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
