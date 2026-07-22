"""Pydantic models describing the FlowPilot flow file format (see PRD §8)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# All node type identifiers recognised by the engine.
NODE_TYPES = {
    "start",
    "end",
    # mouse
    "mouse_move",
    "mouse_down",
    "mouse_up",
    "mouse_click",
    "mouse_scroll",
    # keyboard
    "key_down",
    "key_up",
    "key_press",
    "type_text",
    "shortcut",
    # flow control
    "wait",
    "image_condition",
    "counter_condition",
    # screen
    "screenshot",
    # functions (reusable named sub-graphs)
    "function_start",
    "call_function",
    "function_return",
    # variables & clipboard
    "set_variable",
    "copy_to_variable",
    "paste_variable",
    "prompt_input",
}

# Node types that branch (two outgoing ports: yes / no).
CONDITION_TYPES = {"image_condition", "counter_condition"}

# Node types that end a path and so may not have outgoing edges.
TERMINAL_TYPES = {"end", "function_return"}


class FlowInput(BaseModel):
    name: str
    default: str = ""
    label: str = ""


class FlowSettings(BaseModel):
    start_delay_ms: int = 3000
    max_duration_ms: int = 1800000
    loop_guard_iterations: int = 10000
    failsafe: bool = True


class Node(BaseModel):
    id: str
    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    # UI-only positioning, ignored by the engine.
    position: Optional[dict[str, float]] = None
    label: Optional[str] = None


class Edge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    port: Optional[Literal["yes", "no", "out"]] = None

    model_config = {"populate_by_name": True}


class Flow(BaseModel):
    name: str
    version: int = 1
    inputs: list[FlowInput] = Field(default_factory=list)
    settings: FlowSettings = Field(default_factory=FlowSettings)
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    def to_json_dict(self) -> dict[str, Any]:
        """Serialise using the on-disk shape (edges use `from`, not `from_`)."""
        return self.model_dump(by_alias=True, exclude_none=True)


class ValidationIssue(BaseModel):
    level: Literal["error", "warning"]
    message: str
    node_id: Optional[str] = None


def validate_flow(flow: Flow) -> list[ValidationIssue]:
    """Structural validation per PRD §4.1."""
    issues: list[ValidationIssue] = []
    node_ids = [n.id for n in flow.nodes]
    id_set = set(node_ids)

    # Unknown node types.
    for n in flow.nodes:
        if n.type not in NODE_TYPES:
            issues.append(ValidationIssue(level="error", message=f"Unknown node type '{n.type}'", node_id=n.id))

    # Duplicate ids.
    if len(node_ids) != len(id_set):
        issues.append(ValidationIssue(level="error", message="Duplicate node ids present"))

    # Exactly one start.
    starts = [n for n in flow.nodes if n.type == "start"]
    if len(starts) == 0:
        issues.append(ValidationIssue(level="error", message="Flow has no Start node"))
    elif len(starts) > 1:
        issues.append(ValidationIssue(level="error", message="Flow has more than one Start node"))

    # Edge endpoints must exist.
    for e in flow.edges:
        if e.from_ not in id_set:
            issues.append(ValidationIssue(level="error", message=f"Edge references missing node '{e.from_}'"))
        if e.to not in id_set:
            issues.append(ValidationIssue(level="error", message=f"Edge references missing node '{e.to}'"))

    # Count outgoing edges per node.
    outgoing: dict[str, list[Edge]] = {n.id: [] for n in flow.nodes}
    for e in flow.edges:
        if e.from_ in outgoing:
            outgoing[e.from_].append(e)

    for n in flow.nodes:
        outs = outgoing[n.id]
        if n.type in CONDITION_TYPES:
            ports = {e.port for e in outs}
            if len(outs) > 2:
                issues.append(ValidationIssue(level="error", message="Condition node has more than two outputs", node_id=n.id))
            if not {"yes", "no"} & ports and outs:
                issues.append(ValidationIssue(level="warning", message="Condition node outputs should use 'yes'/'no' ports", node_id=n.id))
        elif n.type in TERMINAL_TYPES:
            if outs:
                label = "End" if n.type == "end" else "Return"
                issues.append(ValidationIssue(level="error", message=f"{label} node cannot have outgoing edges", node_id=n.id))
        else:
            if len(outs) > 1:
                issues.append(ValidationIssue(level="error", message="Action node has more than one outgoing edge", node_id=n.id))

    # --- Functions ---------------------------------------------------------
    func_nodes = [n for n in flow.nodes if n.type == "function_start"]
    func_names: dict[str, str] = {}
    for n in func_nodes:
        name = str(n.params.get("name", "")).strip()
        if not name:
            issues.append(ValidationIssue(level="error", message="Function has no name", node_id=n.id))
            continue
        if name in func_names:
            issues.append(ValidationIssue(level="error", message=f"Duplicate function name '{name}'", node_id=n.id))
        func_names[name] = n.id

    incoming: dict[str, int] = {n.id: 0 for n in flow.nodes}
    for e in flow.edges:
        if e.to in incoming:
            incoming[e.to] += 1
    for n in func_nodes:
        if incoming[n.id]:
            issues.append(ValidationIssue(
                level="warning",
                message="Function entry has an incoming edge; a function is reached by calling it, not by wiring into it",
                node_id=n.id))

    for n in flow.nodes:
        if n.type != "call_function":
            continue
        name = str(n.params.get("name", "")).strip()
        if not name:
            issues.append(ValidationIssue(level="error", message="Call node has no function name", node_id=n.id))
        elif "{" not in name and name not in func_names:
            # Names holding a {var} are resolved at run time, so only literal
            # names can be checked here.
            issues.append(ValidationIssue(level="error", message=f"Call to undefined function '{name}'", node_id=n.id))

    # Orphan nodes: unreachable from Start *or* from any function entry —
    # function bodies are entered by a call, never by an edge from Start.
    if len(starts) == 1:
        roots = [starts[0].id] + [n.id for n in func_nodes]
        reachable: set[str] = set(roots)
        for r in roots:
            reachable |= _reachable_from(r, flow.edges)
        for n in flow.nodes:
            if n.id not in reachable:
                issues.append(ValidationIssue(level="warning", message="Node is not reachable from Start (orphan)", node_id=n.id))

    return issues


def _reachable_from(start_id: str, edges: list[Edge]) -> set[str]:
    adj: dict[str, list[str]] = {}
    for e in edges:
        adj.setdefault(e.from_, []).append(e.to)
    seen: set[str] = set()
    stack = [start_id]
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen
