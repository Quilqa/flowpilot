// Shaded regions drawn behind each function body.
//
// A function is entered by calling it, so its nodes are not reachable from
// Start and would otherwise look like a stray cluster on the canvas. Grouping
// them under a tinted, labelled area makes each function read as its own
// region.

// Used when React Flow has not measured a node yet (it reports width/height
// only after its ResizeObserver fires).
const FALLBACK_W = 150;
const FALLBACK_H = 46;
const PAD = 26;
const TITLE_H = 22;

/** Names of every function defined in the flow, in canvas order. */
export function functionNames(nodes) {
  return nodes
    .filter((n) => n.data?.nodeType === "function_start")
    .map((n) => String(n.data.params?.name || "").trim())
    .filter(Boolean);
}

function adjacency(edges) {
  const adj = new Map();
  for (const e of edges) {
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source).push(e.target);
  }
  return adj;
}

function reachable(startId, adj, stopAt) {
  const seen = new Set();
  const stack = [startId];
  while (stack.length) {
    const cur = stack.pop();
    for (const next of adj.get(cur) || []) {
      if (seen.has(next) || stopAt.has(next)) continue;
      seen.add(next);
      stack.push(next);
    }
  }
  return seen;
}

/**
 * One area box per function, sized to its body.
 *
 * Nodes on the main path are excluded: if a body edges back into the main
 * flow, the area would otherwise stretch across unrelated nodes.
 */
export function computeFunctionAreas(nodes, edges) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const adj = adjacency(edges);

  const startNode = nodes.find((n) => n.data?.nodeType === "start");
  const entries = nodes.filter((n) => n.data?.nodeType === "function_start");
  const entryIds = new Set(entries.map((n) => n.id));

  const mainPath = startNode
    ? reachable(startNode.id, adj, entryIds).add(startNode.id)
    : new Set();

  const claimed = new Set();
  const areas = [];

  for (const entry of entries) {
    // Stop at other entries and at anything already inside the main path or
    // another function, so bodies cannot bleed into each other.
    const stop = new Set([...entryIds, ...mainPath, ...claimed]);
    stop.delete(entry.id);
    const body = reachable(entry.id, adj, stop);
    body.add(entry.id);
    for (const id of body) claimed.add(id);

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const id of body) {
      const n = byId.get(id);
      if (!n) continue;
      const w = n.width || FALLBACK_W;
      const h = n.height || FALLBACK_H;
      minX = Math.min(minX, n.position.x);
      minY = Math.min(minY, n.position.y);
      maxX = Math.max(maxX, n.position.x + w);
      maxY = Math.max(maxY, n.position.y + h);
    }
    if (!Number.isFinite(minX)) continue;

    areas.push({
      id: `__farea_${entry.id}`,
      name: String(entry.data.params?.name || "").trim() || "unnamed",
      nodeCount: body.size,
      position: { x: minX - PAD, y: minY - PAD - TITLE_H },
      width: maxX - minX + PAD * 2,
      height: maxY - minY + PAD * 2 + TITLE_H,
    });
  }

  return areas;
}

/** Wrap the areas as React Flow nodes that sit behind everything else. */
export function areaNodes(areas) {
  return areas.map((a) => ({
    id: a.id,
    type: "functionArea",
    position: a.position,
    data: { name: a.name, width: a.width, height: a.height, nodeCount: a.nodeCount },
    draggable: false,
    selectable: false,
    connectable: false,
    deletable: false,
    focusable: false,
    zIndex: -1,
  }));
}

export const AREA_ID_PREFIX = "__farea_";
