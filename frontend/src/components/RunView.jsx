import { useEffect, useRef, useState } from "react";
import { api, runSocket } from "../api.js";

export default function RunView({ flowName, inputs, onClose, onActiveNode }) {
  const [phase, setPhase] = useState("form"); // form | running | done
  const [vars, setVars] = useState(() =>
    Object.fromEntries((inputs || []).map((i) => [i.name, i.default || ""])));
  const [log, setLog] = useState([]);
  const [liveVars, setLiveVars] = useState({});
  const [paused, setPaused] = useState(false);
  const [result, setResult] = useState(null);
  const wsRef = useRef(null);
  const logEndRef = useRef(null);

  useEffect(() => () => { wsRef.current?.close(); onActiveNode?.(null); }, []);
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [log]);

  const addLog = (line, cls = "") => setLog((l) => [...l, { line, cls, t: Date.now() + Math.random() }]);

  const start = async () => {
    setPhase("running");
    setLog([]);
    const ws = runSocket();
    wsRef.current = ws;
    ws.onopen = async () => {
      try {
        await api.run(flowName, vars);
      } catch (e) {
        addLog(`Failed to start: ${e.message}`, "err");
        setPhase("done");
      }
    };
    ws.onmessage = (ev) => handleEvent(JSON.parse(ev.data));
    ws.onerror = () => addLog("WebSocket error", "err");
  };

  const handleEvent = (e) => {
    switch (e.type) {
      case "countdown": addLog(`Starting in ${Math.round(e.ms / 1000)}s…`, "muted"); break;
      case "run_start": addLog(`▶ Run started: ${e.flow}`, "ok"); break;
      case "node_enter": onActiveNode?.(e.node_id); addLog(`● ${e.node_type} (${e.node_id})`); break;
      case "node_exit": if (e.port) addLog(`   → ${e.port}`, "muted"); break;
      case "condition_check":
        addLog(`   check: ${e.comparison || `confidence ${e.confidence}`} → ${e.found ? "YES" : "no"}`,
          e.found ? "ok" : "muted"); break;
      case "variable_set":
        setLiveVars((v) => ({ ...v, [e.name]: e.value }));
        addLog(`   set ${e.name} = ${e.value}`, "muted"); break;
      case "wait": addLog(`   wait ${e.ms}ms`, "muted"); break;
      case "screenshot": addLog(`   📷 saved ${String(e.path).split(/[\\/]/).pop()}`, "ok"); break;
      case "paused": setPaused(true); addLog("⏸ Paused", "warn"); break;
      case "resumed": setPaused(false); addLog("▶ Resumed", "ok"); break;
      case "error": addLog(`⛔ ${e.message}`, "err"); break;
      case "aborted": addLog("■ Aborted", "err"); break;
      case "run_end":
        addLog(`✔ Finished (exit ${e.exit_code})`, e.exit_code === 0 ? "ok" : "err");
        setResult({ exit_code: e.exit_code }); break;
      case "run_finished":
        setPhase("done"); onActiveNode?.(null); wsRef.current?.close(); break;
      default: break;
    }
  };

  const control = (action) => {
    try { wsRef.current?.send(JSON.stringify({ action })); } catch {}
    if (action === "pause") setPaused(true);
    if (action === "resume") setPaused(false);
  };

  return (
    <div className="modal-overlay">
      <div className="modal run-modal" onClick={(e) => e.stopPropagation()}>
        <div className="run-header">
          <h3>Run — {flowName}</h3>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>

        {phase === "form" && (
          <div className="run-form">
            {inputs?.length > 0 ? (
              <>
                <p className="muted">Fill input variables:</p>
                {inputs.map((i) => (
                  <div className="field" key={i.name}>
                    <label>{i.label || i.name}</label>
                    <input value={vars[i.name] ?? ""} onChange={(e) => setVars((v) => ({ ...v, [i.name]: e.target.value }))} />
                  </div>
                ))}
              </>
            ) : <p className="muted">No inputs. The run begins after a short countdown so you can focus the target app.</p>}
            <div className="modal-actions">
              <button className="btn" onClick={onClose}>Cancel</button>
              <button className="btn run" onClick={start}>▶ Start run</button>
            </div>
            <p className="hint">Panic hotkey <b>Ctrl+Alt+Esc</b> aborts any run. Move the mouse to a screen corner to trigger the failsafe.</p>
          </div>
        )}

        {phase !== "form" && (
          <>
            <div className="run-controls">
              {phase === "running" && !paused && <button className="btn small" onClick={() => control("pause")}>⏸ Pause</button>}
              {phase === "running" && paused && <button className="btn small" onClick={() => control("resume")}>▶ Resume</button>}
              {phase === "running" && <button className="btn small danger" onClick={() => control("stop")}>■ Stop</button>}
              {phase === "done" && <button className="btn small primary" onClick={onClose}>Close</button>}
              {result && <span className={`run-result ${result.exit_code === 0 ? "ok" : "err"}`}>exit {result.exit_code}</span>}
            </div>
            <div className="run-log">
              {log.map((l) => <div key={l.t} className={`log-line ${l.cls}`}>{l.line}</div>)}
              <div ref={logEndRef} />
            </div>
            {Object.keys(liveVars).length > 0 && (
              <div className="var-panel">
                <div className="var-title">Variables</div>
                {Object.entries(liveVars).map(([k, v]) => (
                  <div className="var-row" key={k}><span className="mono">{k}</span><span>{v}</span></div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
