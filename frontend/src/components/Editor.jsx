import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background, Controls, MiniMap, addEdge,
  useNodesState, useEdgesState,
} from "reactflow";
import { api } from "../api.js";
import { buildPaste, copySelection, makeEdge, parseClip } from "../clipboard.js";
import { areaNodes, computeFunctionAreas, functionNames } from "../functions.js";
import { NODE_DEFS, defaultParams, isCondition } from "../nodeTypes.js";
import { nodeSummary } from "../summary.js";
import FlowNode from "./FlowNode.jsx";
import FunctionArea from "./FunctionArea.jsx";
import NodePalette from "./NodePalette.jsx";
import ParamPanel from "./ParamPanel.jsx";
import RunView from "./RunView.jsx";
import SettingsPanel from "./SettingsPanel.jsx";

const nodeTypes = { flowNode: FlowNode, functionArea: FunctionArea };
let idSeq = 1;
const newId = () => `n${Date.now()}_${idSeq++}`;

function flowToRf(flow) {
  const nodes = flow.nodes.map((n) => ({
    id: n.id,
    type: "flowNode",
    position: n.position || { x: 200, y: 100 },
    data: { nodeType: n.type, params: n.params || {}, summary: nodeSummary(n.type, n.params || {}) },
  }));
  const edges = flow.edges.map((e, i) => makeEdge(e.from, e.to, e.port, `e${i}_${e.from}_${e.to}`));
  return { nodes, edges };
}

function rfToFlow(meta, nodes, edges) {
  return {
    ...meta,
    nodes: nodes.map((n) => ({
      id: n.id, type: n.data.nodeType, params: n.data.params || {},
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
    })),
    edges: edges.map((e) => ({
      from: e.source, to: e.target,
      ...(e.sourceHandle === "yes" || e.sourceHandle === "no" ? { port: e.sourceHandle } : {}),
    })),
  };
}

export default function Editor({ flowName, onBack }) {
  const [meta, setMeta] = useState(null); // name, version, inputs, settings
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [running, setRunning] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [status, setStatus] = useState("");
  const [issues, setIssues] = useState([]);
  const wrapRef = useRef(null);
  const dirtyRef = useRef(false);

  // Load flow.
  useEffect(() => {
    (async () => {
      const flow = await api.getFlow(flowName);
      const { nodes, edges } = flowToRf(flow);
      setNodes(nodes);
      setEdges(edges);
      setMeta({ name: flow.name, version: flow.version, inputs: flow.inputs || [], settings: flow.settings || {} });
    })();
  }, [flowName, setNodes, setEdges]);

  const markDirty = useCallback(() => { dirtyRef.current = true; }, []);

  const onConnect = useCallback((conn) => {
    const srcNode = nodes.find((n) => n.id === conn.source);
    const cond = srcNode && isCondition(srcNode.data.nodeType);
    // Enforce single outgoing edge for non-condition, single per-port for conditions.
    setEdges((eds) => {
      let filtered = eds;
      if (cond) {
        filtered = eds.filter((e) => !(e.source === conn.source && e.sourceHandle === conn.sourceHandle));
      } else {
        filtered = eds.filter((e) => e.source !== conn.source);
      }
      return addEdge({ ...conn, ...makeEdge(conn.source, conn.target, conn.sourceHandle) }, filtered);
    });
    markDirty();
  }, [nodes, setEdges, markDirty]);

  const addNode = useCallback((type, pos) => {
    const id = newId();
    const params = defaultParams(type);
    const position = pos || { x: 250 + Math.random() * 120, y: 120 + Math.random() * 160 };
    setNodes((nds) => nds.concat({
      id, type: "flowNode", position,
      data: { nodeType: type, params, summary: nodeSummary(type, params) },
    }));
    setSelectedId(id);
    markDirty();
  }, [setNodes, markDirty]);

  const onDrop = useCallback((event) => {
    event.preventDefault();
    const type = event.dataTransfer.getData("application/flowpilot");
    if (!type || !wrapRef.current) return;
    const bounds = wrapRef.current.getBoundingClientRect();
    addNode(type, { x: event.clientX - bounds.left - 60, y: event.clientY - bounds.top - 20 });
  }, [addNode]);

  const updateParams = useCallback((id, params) => {
    setNodes((nds) => nds.map((n) => n.id === id
      ? { ...n, data: { ...n.data, params, summary: nodeSummary(n.data.nodeType, params) } }
      : n));
    markDirty();
  }, [setNodes, markDirty]);

  const deleteNode = useCallback((id) => {
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
    setSelectedId(null);
    markDirty();
  }, [setNodes, setEdges, markDirty]);

  // --- Copy / paste of node sub-graphs -----------------------------------
  // The system clipboard carries the payload, so a construct copied here can
  // be pasted into a different flow. clipRef is the in-session fallback for
  // when the browser hands us no clipboard text.
  const clipRef = useRef(null);
  const pasteSeqRef = useRef(0);
  const clipSigRef = useRef("");

  const copyNow = useCallback(() => {
    const clip = copySelection(nodes, edges);
    if (!clip) {
      setStatus("Nothing to copy — select node(s) first (Shift+drag for several)");
      return null;
    }
    clipRef.current = clip;
    const parts = [`Copied ${clip.nodes.length} node${clip.nodes.length > 1 ? "s" : ""}`];
    if (clip.edges.length) parts.push(`${clip.edges.length} connection${clip.edges.length > 1 ? "s" : ""}`);
    if (clip.skippedStart) parts.push("Start skipped");
    setStatus(parts.join(" · "));
    return clip;
  }, [nodes, edges]);

  const pasteClip = useCallback((clip) => {
    // Stagger repeated pastes of the same payload so copies don't stack up
    // exactly on top of each other.
    const sig = JSON.stringify(clip.nodes.map((n) => n.id));
    if (sig !== clipSigRef.current) { clipSigRef.current = sig; pasteSeqRef.current = 0; }
    pasteSeqRef.current += 1;
    const d = 40 * pasteSeqRef.current;

    const { nodes: added, edges: addedEdges } = buildPaste(clip, { x: d, y: d }, newId);
    // The paste becomes the new selection, so it can be dragged straight away.
    setNodes((nds) => nds.map((n) => (n.selected ? { ...n, selected: false } : n)).concat(added));
    setEdges((eds) => eds.concat(addedEdges));
    setSelectedId(added.length === 1 ? added[0].id : null);
    markDirty();
    setStatus(`Pasted ${added.length} node${added.length > 1 ? "s" : ""}`);
  }, [setNodes, setEdges, markDirty]);

  useEffect(() => {
    // Never hijack copy/paste while the caret is in a parameter field.
    const editable = (t) => !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);

    const onCopy = (e) => {
      if (editable(e.target)) return;
      const clip = copyNow();
      if (!clip) return; // nothing selected: let the browser copy normally
      e.preventDefault();
      e.clipboardData?.setData("text/plain", JSON.stringify(clip));
    };

    const onPaste = (e) => {
      if (editable(e.target)) return;
      const clip = parseClip(e.clipboardData?.getData("text/plain")) || clipRef.current;
      if (!clip) return; // unrelated clipboard content: leave it alone
      e.preventDefault();
      pasteClip(clip);
    };

    const onKey = (e) => {
      if (editable(e.target)) return;
      if ((e.ctrlKey || e.metaKey) && (e.key === "d" || e.key === "D")) {
        e.preventDefault(); // browsers bind Ctrl+D to bookmark
        const clip = copyNow();
        if (clip) pasteClip(clip);
      }
    };

    window.addEventListener("copy", onCopy);
    window.addEventListener("paste", onPaste);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("copy", onCopy);
      window.removeEventListener("paste", onPaste);
      window.removeEventListener("keydown", onKey);
    };
  }, [copyNow, pasteClip]);

  const save = useCallback(async () => {
    if (!meta) return;
    const flow = rfToFlow(meta, nodes, edges);
    try {
      const res = await api.saveFlow(flow);
      setIssues(res.issues || []);
      dirtyRef.current = false;
      setStatus(`Saved ${new Date().toLocaleTimeString()}`);
    } catch (e) {
      setStatus(`Save failed: ${e.message}`);
    }
  }, [meta, nodes, edges]);

  // Ctrl+S + delete key.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); save(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save]);

  // Auto-save every 30s if dirty.
  useEffect(() => {
    const t = setInterval(() => { if (dirtyRef.current) save(); }, 30000);
    return () => clearInterval(t);
  }, [save]);

  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedId) || null, [nodes, selectedId]);
  const fnNames = useMemo(() => functionNames(nodes), [nodes]);

  // Function backdrops are derived from the graph, never part of `nodes`
  // state — so they cannot be selected, copied, or written to the flow file.
  const canvasNodes = useMemo(
    () => [...areaNodes(computeFunctionAreas(nodes, edges)), ...nodes],
    [nodes, edges],
  );

  if (!meta) return <div className="screen"><p className="muted">Loading…</p></div>;

  return (
    <div className="editor">
      <div className="editor-toolbar">
        <button className="btn small" onClick={onBack}>← Flows</button>
        <span className="editor-title">{meta.name}</span>
        <div className="spacer" />
        <span className="shortcut-hint" title="Shift+drag to box-select. Ctrl+C / Ctrl+V copies nodes with the connections between them — across flows too. Ctrl+D duplicates in place.">
          Shift+drag select · Ctrl+C/V copy · Ctrl+D duplicate
        </span>
        <span className="status-text">{status}</span>
        <button className="btn small" onClick={() => setShowSettings(true)}>⚙ Settings</button>
        <button className="btn small primary" onClick={save}>Save</button>
        <button className="btn small run" onClick={async () => { await save(); setRunning(true); }}>▶ Run</button>
      </div>

      {issues.filter((i) => i.level === "error").length > 0 && (
        <div className="error-banner">
          {issues.filter((i) => i.level === "error").map((i, k) => <div key={k}>⛔ {i.message}</div>)}
        </div>
      )}

      <div className="editor-body">
        <NodePalette onAdd={addNode} />
        <div className="canvas-wrap" ref={wrapRef}
             onDrop={onDrop} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }}>
          <ReactFlow
            nodes={canvasNodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={(c) => { onNodesChange(c); if (c.some((x) => x.type === "position" || x.type === "remove")) markDirty(); }}
            onEdgesChange={(c) => { onEdgesChange(c); if (c.some((x) => x.type === "remove")) markDirty(); }}
            onConnect={onConnect}
            onNodeClick={(_, n) => setSelectedId(n.id)}
            onPaneClick={() => setSelectedId(null)}
            fitView
            deleteKeyCode={["Delete", "Backspace"]}
          >
            <Background gap={16} />
            <Controls />
            <MiniMap pannable zoomable nodeColor={(n) => NODE_DEFS[n.data?.nodeType]?.color || "#64748b"} />
          </ReactFlow>
        </div>
        {selectedNode && (
          <ParamPanel
            node={selectedNode}
            flowName={meta.name}
            functionNames={fnNames}
            onChange={(params) => updateParams(selectedNode.id, params)}
            onDelete={() => deleteNode(selectedNode.id)}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>

      {showSettings && (
        <SettingsPanel meta={meta} onChange={(m) => { setMeta(m); markDirty(); }} onClose={() => setShowSettings(false)} />
      )}
      {running && (
        <RunView flowName={meta.name} inputs={meta.inputs} nodes={nodes}
                 onClose={() => setRunning(false)}
                 onActiveNode={(id) => setNodes((nds) => nds.map((n) => ({ ...n, data: { ...n.data, active: n.id === id } })))} />
      )}
    </div>
  );
}
