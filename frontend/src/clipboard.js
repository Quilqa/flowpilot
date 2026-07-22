// Copy/paste of node sub-graphs.
//
// A copied selection carries the nodes *and* the edges between them, so a
// multi-node construct (a counter loop, an alt-tab scan…) can be pasted into
// another flow without rebuilding the wiring by hand. The payload is plain
// JSON on the system clipboard, which makes it portable across flows, browser
// tabs, and sessions.

import { MarkerType } from "reactflow";
import { nodeSummary } from "./summary.js";

// Bump if the payload shape ever changes, so old clipboard text is rejected
// rather than pasted as garbage.
export const CLIP_KIND = "flowpilot/nodes@1";

const clone = (o) => JSON.parse(JSON.stringify(o ?? {}));

let edgeSeq = 1;
const newEdgeId = () => `e${Date.now()}_${edgeSeq++}`;

/** Build a styled React Flow edge. Shared by load, connect, and paste so the
 *  three paths cannot drift apart. */
export function makeEdge(source, target, port, id) {
  const p = port === "yes" || port === "no" ? port : null;
  return {
    id: id || newEdgeId(),
    source,
    target,
    sourceHandle: p,
    label: p === "yes" ? "Yes" : p === "no" ? "No" : undefined,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { stroke: p === "yes" ? "#16a34a" : p === "no" ? "#dc2626" : "#94a3b8" },
  };
}

/**
 * Snapshot the current selection.
 *
 * Start nodes are skipped: a flow must have exactly one, so pasting a second
 * would only produce a validation error. Returns null when there is nothing
 * copyable.
 */
export function copySelection(nodes, edges) {
  const selected = nodes.filter((n) => n.selected);
  const copyable = selected.filter((n) => n.data.nodeType !== "start");
  if (copyable.length === 0) return null;

  const ids = new Set(copyable.map((n) => n.id));
  // Only edges fully inside the selection — a dangling edge has no valid
  // endpoint once pasted.
  const internal = edges.filter((e) => ids.has(e.source) && ids.has(e.target));

  return {
    kind: CLIP_KIND,
    skippedStart: selected.length - copyable.length,
    nodes: copyable.map((n) => ({
      id: n.id,
      nodeType: n.data.nodeType,
      params: clone(n.data.params),
      position: { ...n.position },
    })),
    edges: internal.map((e) => ({
      source: e.source,
      target: e.target,
      port: e.sourceHandle === "yes" || e.sourceHandle === "no" ? e.sourceHandle : null,
    })),
  };
}

/** Parse clipboard text, returning null unless it is a valid payload. */
export function parseClip(text) {
  if (!text || text.length > 5_000_000) return null;
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return null; // ordinary text on the clipboard — not ours
  }
  if (!data || data.kind !== CLIP_KIND || !Array.isArray(data.nodes) || !Array.isArray(data.edges)) {
    return null;
  }
  if (data.nodes.length === 0) return null;
  return data;
}

/**
 * Materialise a payload as fresh nodes/edges.
 *
 * Every node gets a new id and edges are remapped onto those ids, so a paste
 * never collides with or re-points the existing graph. Positions are shifted
 * by `offset` so the copy does not land exactly on top of the original.
 */
export function buildPaste(clip, offset, makeId) {
  const idMap = new Map();

  const nodes = clip.nodes.map((n) => {
    const id = makeId();
    idMap.set(n.id, id);
    const params = clone(n.params);
    return {
      id,
      type: "flowNode",
      position: { x: (n.position?.x || 0) + offset.x, y: (n.position?.y || 0) + offset.y },
      selected: true, // so the paste can be dragged (or re-copied) immediately
      data: { nodeType: n.nodeType, params, summary: nodeSummary(n.nodeType, params) },
    };
  });

  const edges = clip.edges
    .filter((e) => idMap.has(e.source) && idMap.has(e.target))
    .map((e) => makeEdge(idMap.get(e.source), idMap.get(e.target), e.port));

  return { nodes, edges };
}
