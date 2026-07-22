"""Flow execution engine: traverses the graph and runs each node.

Emits structured events via a callback so the UI (WebSocket) and the CLI
runner can both observe progress. Designed to be interruptible (panic/stop).
"""
from __future__ import annotations

import random
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from . import automation, capture, config
from .matching import match_template
from .models import Edge, Flow, Node

# --- Variable interpolation -------------------------------------------------

_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def interpolate(value: Any, variables: dict[str, str]) -> Any:
    """Replace {name} tokens in strings using the variable map."""
    if not isinstance(value, str):
        return value

    def repl(m: re.Match) -> str:
        return str(variables.get(m.group(1), m.group(0)))

    return _VAR_RE.sub(repl, value)


def eval_expression(expr: str, variables: dict[str, str]) -> str:
    """Evaluate a Set Variable expression.

    Supports {a}+1 style numeric arithmetic and string concatenation after
    interpolation. Falls back to the interpolated string if it is not a
    simple arithmetic expression.
    """
    interpolated = interpolate(expr, variables)
    # Only attempt arithmetic if it looks like a simple numeric expression.
    # Reject exponentiation (`**`) — even sandboxed, `9**9**9` can hang the
    # process allocating a giant integer (DoS).
    if re.fullmatch(r"[\d\.\s+\-*/()]+", interpolated or "") and "**" not in interpolated:
        try:
            result = eval(interpolated, {"__builtins__": {}}, {})  # noqa: S307 - sandboxed
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(result)
        except Exception:
            return interpolated
    return interpolated


def coerce_compare(a: str, b: str, op: str) -> bool:
    """Comparison with numeric auto-coercion when both sides are numbers."""
    if op == "contains":
        return str(b) in str(a)

    def num(x: str):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    na, nb = num(a), num(b)
    if na is not None and nb is not None:
        a_val, b_val = na, nb
    else:
        a_val, b_val = str(a), str(b)

    if op == "==":
        return a_val == b_val
    if op == "!=":
        return a_val != b_val
    if op == ">":
        return a_val > b_val
    if op == "<":
        return a_val < b_val
    if op == ">=":
        return a_val >= b_val
    if op == "<=":
        return a_val <= b_val
    raise ValueError(f"Unknown operator: {op}")


# --- Events ----------------------------------------------------------------

EventCallback = Callable[[dict[str, Any]], None]


@dataclass
class RunResult:
    success: bool
    exit_code: int
    message: str = ""
    variables: dict[str, str] = field(default_factory=dict)


class RunAborted(Exception):
    """Raised to unwind execution when stopped or panicked."""


# A function calling itself (directly or in a cycle) would otherwise grow the
# call stack until memory runs out; the loop guard cannot see it because each
# node is entered only once per call.
MAX_CALL_DEPTH = 64


class FlowRunner:
    def __init__(
        self,
        flow: Flow,
        variables: Optional[dict[str, str]] = None,
        on_event: Optional[EventCallback] = None,
        cfg: Optional[dict[str, Any]] = None,
    ):
        self.flow = flow
        self.variables: dict[str, str] = {}
        self.on_event = on_event or (lambda e: None)
        self.cfg = cfg or config.load_config()

        # Seed inputs with defaults, then overlay supplied values.
        for inp in flow.inputs:
            self.variables[inp.name] = inp.default
        if variables:
            self.variables.update({k: str(v) for k, v in variables.items()})

        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.set()  # set == running; cleared == paused
        self._nodes: dict[str, Node] = {n.id: n for n in flow.nodes}
        self._edges = flow.edges
        self._loop_counter: dict[str, int] = {}
        # Functions: name -> entry node id. Bodies are ordinary nodes reached
        # by a call rather than by an edge from Start.
        self._functions: dict[str, str] = {}
        for n in flow.nodes:
            if n.type == "function_start":
                fname = str(n.params.get("name", "")).strip()
                if fname:
                    self._functions.setdefault(fname, n.id)
        # Node ids to resume at, innermost call last.
        self._call_stack: list[Optional[str]] = []

    # --- control -----------------------------------------------------------

    def stop(self) -> None:
        self._stop.set()
        self._pause.set()  # release any pause wait

    def pause(self) -> None:
        self._pause.clear()

    def resume(self) -> None:
        self._pause.set()

    def _check_control(self) -> None:
        if self._stop.is_set():
            raise RunAborted()
        # Block while paused (unless stopping).
        while not self._pause.is_set() and not self._pause.wait(0.05):
            if self._stop.is_set():
                raise RunAborted()

    def _sleep(self, ms: int) -> None:
        """Interruptible sleep."""
        end = time.monotonic() + ms / 1000.0
        while time.monotonic() < end:
            self._check_control()
            time.sleep(min(0.05, max(0, end - time.monotonic())))

    # --- events ------------------------------------------------------------

    def emit(self, kind: str, **data: Any) -> None:
        evt = {"type": kind, "ts": time.time(), **data}
        self.on_event(evt)

    # --- traversal ---------------------------------------------------------

    def _next_node_id(self, node_id: str, port: Optional[str] = None) -> Optional[str]:
        candidates: list[Edge] = [e for e in self._edges if e.from_ == node_id]
        if port is not None:
            for e in candidates:
                if e.port == port:
                    return e.to
            return None
        # non-condition: take the first (should be only) edge
        for e in candidates:
            return e.to
        return None

    def run(self) -> RunResult:
        self.variables.setdefault("_start", "1")
        start = next((n for n in self.flow.nodes if n.type == "start"), None)
        if start is None:
            self.emit("error", message="No Start node")
            return RunResult(False, 2, "No Start node", self.variables)

        automation.set_failsafe(self.flow.settings.failsafe)

        start_delay = self.flow.settings.start_delay_ms
        if start_delay:
            self.emit("countdown", ms=start_delay)
            try:
                self._sleep(start_delay)
            except RunAborted:
                return self._aborted()

        deadline = time.monotonic() + (self.flow.settings.max_duration_ms / 1000.0)
        loop_guard = self.flow.settings.loop_guard_iterations or self.cfg.get("loop_guard_iterations", 10000)

        self.emit("run_start", flow=self.flow.name)
        current: Optional[str] = start.id
        try:
            while current is not None:
                self._check_control()
                if time.monotonic() > deadline:
                    self.emit("error", message="Max run duration exceeded")
                    return RunResult(False, 3, "Max duration exceeded", self.variables)

                self._loop_counter[current] = self._loop_counter.get(current, 0) + 1
                if self._loop_counter[current] > loop_guard:
                    self.emit("error", message=f"Loop guard tripped at node {current}")
                    return RunResult(False, 4, "Loop guard tripped", self.variables)

                node = self._nodes[current]
                self.emit("node_enter", node_id=node.id, node_type=node.type)
                port, result = self._execute(node)
                self.emit("node_exit", node_id=node.id, port=port)

                # Loop guard targets *runaway* cycles (PRD §7.4) — a cycle that
                # spins with no intervening Wait. A Wait means the loop is
                # deliberately paced (e.g. long-poll), so reset the counters.
                if node.type == "wait":
                    self._loop_counter.clear()

                if node.type == "end":
                    code = int(result) if result is not None else 0
                    self.emit("run_end", exit_code=code, variables=self.variables)
                    return RunResult(code == 0, code, "Reached End node", self.variables)

                if node.type == "call_function":
                    current = self._do_call(node)
                    continue

                if node.type == "function_return":
                    current = self._return_to_caller()
                    continue

                nxt = self._next_node_id(node.id, port)
                if nxt is None and self._call_stack:
                    # A function body that runs out of nodes returns, rather
                    # than ending the whole flow.
                    nxt = self._return_to_caller()
                current = nxt

            # Dead-end = normal completion.
            self.emit("run_end", exit_code=0, variables=self.variables)
            return RunResult(True, 0, "Flow completed", self.variables)

        except RunAborted:
            return self._aborted()
        except Exception as exc:  # noqa: BLE001 - report any node failure
            self.emit("error", message=f"{type(exc).__name__}: {exc}")
            return RunResult(False, 1, str(exc), self.variables)

    # --- function calls ----------------------------------------------------

    def _do_call(self, node: Node) -> Optional[str]:
        """Enter a function, remembering where to resume afterwards."""
        name = str(self._p(node, "name", "")).strip()
        target = self._functions.get(name)
        if target is None:
            raise ValueError(f"Call to undefined function '{name}'")
        if len(self._call_stack) >= MAX_CALL_DEPTH:
            raise RecursionError(
                f"Function call depth exceeded ({MAX_CALL_DEPTH}) while calling '{name}' — check for recursion")
        # May be None when nothing follows the call; _return_to_caller unwinds
        # past those so an outer caller still resumes correctly.
        self._call_stack.append(self._next_node_id(node.id))
        self.emit("function_enter", node_id=node.id, name=name, depth=len(self._call_stack))
        return target

    def _return_to_caller(self) -> Optional[str]:
        """Pop back to the nearest caller that still has work left."""
        while self._call_stack:
            resume = self._call_stack.pop()
            self.emit("function_return", depth=len(self._call_stack))
            if resume is not None:
                return resume
        return None

    def _aborted(self) -> RunResult:
        self.emit("aborted", variables=self.variables)
        return RunResult(False, 130, "Aborted", self.variables)

    # --- node execution ----------------------------------------------------

    def _p(self, node: Node, key: str, default: Any = None) -> Any:
        """Fetch a param with variable interpolation applied to strings."""
        val = node.params.get(key, default)
        return interpolate(val, self.variables)

    def _int(self, node: Node, key: str, default: int = 0) -> int:
        try:
            return int(float(self._p(node, key, default)))
        except (TypeError, ValueError):
            return default

    def _opt_int(self, node: Node, key: str) -> Optional[int]:
        raw = node.params.get(key, None)
        if raw is None or raw == "":
            return None
        try:
            return int(float(interpolate(raw, self.variables)))
        except (TypeError, ValueError):
            return None

    def _execute(self, node: Node) -> tuple[Optional[str], Any]:
        """Run one node. Returns (output_port, extra_result)."""
        t = node.type

        # Markers handled by the traversal loop, not by executing anything.
        if t in ("start", "function_start", "call_function", "function_return"):
            return None, None

        if t == "end":
            return None, self._int(node, "exit_code", 0)

        if t == "mouse_move":
            automation.mouse_move(
                self._int(node, "x"), self._int(node, "y"),
                self._int(node, "duration_ms", 0),
                str(node.params.get("easing", "linear")),
                abort_check=self._stop.is_set,
            )
            return None, None

        if t == "mouse_down":
            automation.mouse_down(str(node.params.get("button", "left")), self._opt_int(node, "x"), self._opt_int(node, "y"))
            return None, None

        if t == "mouse_up":
            automation.mouse_up(str(node.params.get("button", "left")), self._opt_int(node, "x"), self._opt_int(node, "y"))
            return None, None

        if t == "mouse_click":
            automation.mouse_click(
                str(node.params.get("button", "left")),
                self._opt_int(node, "x"), self._opt_int(node, "y"),
                self._int(node, "clicks", 1),
                self._int(node, "interval_ms", 0),
            )
            return None, None

        if t == "mouse_scroll":
            automation.mouse_scroll(str(node.params.get("direction", "down")), self._int(node, "amount", 3))
            return None, None

        if t == "key_down":
            automation.key_down(str(self._p(node, "key", "")))
            return None, None

        if t == "key_up":
            automation.key_up(str(self._p(node, "key", "")))
            return None, None

        if t == "key_press":
            automation.key_press(str(self._p(node, "key", "")), self._int(node, "hold_ms", 80))
            return None, None

        if t == "type_text":
            automation.type_text(str(self._p(node, "text", "")), self._int(node, "delay_ms", 0))
            return None, None

        if t == "shortcut":
            automation.shortcut(str(node.params.get("preset", "")), str(self._p(node, "custom_combo", "")))
            return None, None

        if t == "wait":
            self._do_wait(node)
            return None, None

        if t == "screenshot":
            self._do_screenshot(node)
            return None, None

        if t == "image_condition":
            return self._do_image_condition(node), None

        if t == "counter_condition":
            return self._do_counter_condition(node), None

        if t == "set_variable":
            name = str(node.params.get("name", "")).strip()
            if name:
                self.variables[name] = eval_expression(str(node.params.get("value", "")), self.variables)
                self.emit("variable_set", name=name, value=self.variables[name])
            return None, None

        if t == "copy_to_variable":
            name = str(node.params.get("name") or "copied_text")
            self.variables[name] = automation.copy_selection_to_clipboard()
            self.emit("variable_set", name=name, value=self.variables[name])
            return None, None

        if t == "paste_variable":
            name = str(node.params.get("name") or "copied_text")
            automation.paste_value(self.variables.get(name, ""))
            return None, None

        if t == "prompt_input":
            # Values already supplied via inputs/CLI/UI before run; no-op at runtime.
            return None, None

        self.emit("error", message=f"Unhandled node type '{t}'")
        return None, None

    def _do_wait(self, node: Node) -> None:
        if node.params.get("random"):
            lo = self._int(node, "min_ms", 0)
            hi = self._int(node, "max_ms", lo)
            ms = random.randint(min(lo, hi), max(lo, hi))
        else:
            ms = self._int(node, "duration_ms", 0)
        self.emit("wait", ms=ms)
        self._sleep(ms)

    def _do_screenshot(self, node: Node) -> None:
        """Save a PNG of the screen (or a region) into screenshots/."""
        # Milliseconds are included so a screenshot inside a loop does not
        # overwrite the previous iteration's file.
        stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
        raw = str(self._p(node, "filename", "")).strip()
        # `{timestamp}` is resolved here rather than from the variable map, so
        # it works without the flow declaring anything. A user variable of the
        # same name wins, since interpolation already ran.
        raw = raw.replace("{timestamp}", stamp)
        if not raw:
            raw = f"{self.flow.name}_{stamp}"

        path = config.SCREENSHOTS_DIR / config.safe_filename(raw, ".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = capture.capture_png(self._region(node))
        path.write_bytes(data)

        var = str(node.params.get("variable") or "screenshot_path").strip()
        if var:
            self.variables[var] = str(path)
            self.emit("variable_set", name=var, value=str(path))
        self.emit("screenshot", node_id=node.id, path=str(path), bytes=len(data))

    def _do_image_condition(self, node: Node) -> str:
        p = node.params
        template = str(self._p(node, "template", ""))
        tpath = Path(template)
        if not tpath.is_absolute():
            tpath = config.ROOT / template
        conf = float(p.get("confidence", self.cfg.get("default_confidence", 0.85)))
        grayscale = bool(p.get("grayscale", True))
        region = self._region(node)
        mode = p.get("mode", "once")

        def do_match():
            return match_template(tpath, conf, region, grayscale)

        if mode == "poll":
            interval = self._int(node, "interval_ms", self.cfg.get("default_poll_interval_ms", 250))
            timeout = self._int(node, "timeout_ms", self.cfg.get("default_poll_timeout_ms", 5000))
            end = time.monotonic() + timeout / 1000.0
            last = None
            while True:
                self._check_control()
                last = do_match()
                self.emit("condition_check", node_id=node.id, confidence=round(last.confidence, 4), found=last.found)
                if last.found:
                    self._store_match(last)
                    return "yes"
                if time.monotonic() >= end:
                    return "no"
                self._sleep(interval)
        else:
            res = do_match()
            self.emit("condition_check", node_id=node.id, confidence=round(res.confidence, 4), found=res.found)
            if res.found:
                self._store_match(res)
                return "yes"
            return "no"

    def _store_match(self, res) -> None:
        self.variables["match_x"] = str(res.x)
        self.variables["match_y"] = str(res.y)
        self.variables["match_confidence"] = str(round(res.confidence, 4))
        self.emit("variable_set", name="match_x", value=self.variables["match_x"])
        self.emit("variable_set", name="match_y", value=self.variables["match_y"])

    def _do_counter_condition(self, node: Node) -> str:
        left = str(self._p(node, "variable", ""))
        # `variable` may be a var name or an interpolated value; prefer the raw var if it exists.
        raw_name = str(node.params.get("variable", "")).strip()
        if raw_name in self.variables:
            left = self.variables[raw_name]
        op = str(node.params.get("operator", "=="))
        right = str(self._p(node, "value", ""))
        result = coerce_compare(left, right, op)
        self.emit("condition_check", node_id=node.id, comparison=f"{left} {op} {right}", found=result)
        return "yes" if result else "no"

    def _region(self, node: Node) -> Optional[tuple[int, int, int, int]]:
        r = node.params.get("region")
        if not r:
            return None
        try:
            return (int(r["left"]), int(r["top"]), int(r["width"]), int(r["height"]))
        except (KeyError, TypeError, ValueError):
            return None
