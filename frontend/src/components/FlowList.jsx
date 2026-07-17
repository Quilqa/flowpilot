import { useEffect, useState, useCallback } from "react";
import { api } from "../api.js";

export default function FlowList({ onOpen }) {
  const [flows, setFlows] = useState([]);
  const [error, setError] = useState("");
  const [cli, setCli] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setFlows(await api.listFlows());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const createFlow = async () => {
    const name = prompt("New flow name:", "my_flow");
    if (!name) return;
    await api.saveFlow({
      name,
      version: 1,
      inputs: [],
      settings: { start_delay_ms: 3000, max_duration_ms: 1800000 },
      nodes: [{ id: "start", type: "start", position: { x: 80, y: 120 } }],
      edges: [],
    });
    onOpen(name);
  };

  const act = async (fn) => { try { await fn(); await refresh(); } catch (e) { alert(e.message); } };

  const showCli = async (name) => {
    try { setCli({ name, ...(await api.cliCommand(name)) }); }
    catch (e) { alert(e.message); }
  };

  return (
    <div className="screen list-screen">
      <div className="list-header">
        <h1>Flows</h1>
        <button className="btn primary" onClick={createFlow}>+ New Flow</button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      {flows.length === 0 && !error && <p className="muted">No flows yet. Create one to get started.</p>}
      <div className="flow-grid">
        {flows.map((f) => (
          <div className="flow-card" key={f.file}>
            <div className="flow-card-title">{f.name}</div>
            <div className="flow-card-meta">{f.nodes} node{f.nodes !== 1 ? "s" : ""}
              {f.inputs?.length ? ` · ${f.inputs.length} input${f.inputs.length !== 1 ? "s" : ""}` : ""}</div>
            <div className="flow-card-actions">
              <button className="btn small primary" onClick={() => onOpen(f.name)}>Edit</button>
              <button className="btn small" onClick={() => act(async () => {
                const nn = prompt("Duplicate as:", `${f.name} copy`);
                if (nn) await api.duplicateFlow(f.name, nn);
              })}>Duplicate</button>
              <button className="btn small" onClick={() => act(async () => {
                const nn = prompt("Rename to:", f.name);
                if (nn && nn !== f.name) await api.renameFlow(f.name, nn);
              })}>Rename</button>
              <button className="btn small" onClick={() => showCli(f.name)}>CLI</button>
              <button className="btn small danger" onClick={() => act(async () => {
                if (confirm(`Delete flow "${f.name}"? This also removes its templates.`))
                  await api.deleteFlow(f.name);
              })}>Delete</button>
            </div>
          </div>
        ))}
      </div>

      {cli && (
        <div className="modal-overlay" onClick={() => setCli(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Task Scheduler command — {cli.name}</h3>
            <p className="muted">Paste as the "Program/script" action. Set "Start in" to the working directory.
              Requires "Run only when user is logged on".</p>
            <label>Command</label>
            <code className="code-block">{cli.command}</code>
            <label>Working directory (Start in)</label>
            <code className="code-block">{cli.cwd}</code>
            <div className="modal-actions">
              <button className="btn" onClick={() => navigator.clipboard.writeText(cli.command)}>Copy command</button>
              <button className="btn primary" onClick={() => setCli(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
