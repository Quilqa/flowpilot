import { useState } from "react";

export default function SettingsPanel({ meta, onChange, onClose }) {
  const [local, setLocal] = useState({
    ...meta,
    settings: {
      start_delay_ms: 3000, max_duration_ms: 1800000, loop_guard_iterations: 10000, failsafe: true,
      ...(meta.settings || {}),
    },
    inputs: meta.inputs || [],
  });

  const setS = (k, v) => setLocal((m) => ({ ...m, settings: { ...m.settings, [k]: v } }));
  const setInput = (i, k, v) => setLocal((m) => {
    const inputs = m.inputs.map((inp, idx) => idx === i ? { ...inp, [k]: v } : inp);
    return { ...m, inputs };
  });
  const addInput = () => setLocal((m) => ({ ...m, inputs: [...m.inputs, { name: `input${m.inputs.length + 1}`, default: "", label: "" }] }));
  const removeInput = (i) => setLocal((m) => ({ ...m, inputs: m.inputs.filter((_, idx) => idx !== i) }));

  const apply = () => { onChange(local); onClose(); };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Flow settings — {meta.name}</h3>

        <div className="field">
          <label>Start delay (ms)</label>
          <input type="number" value={local.settings.start_delay_ms}
                 onChange={(e) => setS("start_delay_ms", Number(e.target.value))} />
          <span className="hint">Countdown before the run begins, so you can focus the target app.</span>
        </div>
        <div className="field">
          <label>Max run duration (ms)</label>
          <input type="number" value={local.settings.max_duration_ms}
                 onChange={(e) => setS("max_duration_ms", Number(e.target.value))} />
        </div>
        <div className="field">
          <label>Loop guard (iterations)</label>
          <input type="number" value={local.settings.loop_guard_iterations}
                 onChange={(e) => setS("loop_guard_iterations", Number(e.target.value))} />
        </div>
        <div className="field checkbox-field">
          <label><input type="checkbox" checked={local.settings.failsafe}
                        onChange={(e) => setS("failsafe", e.target.checked)} /> pyautogui failsafe (corner-abort)</label>
        </div>

        <div className="settings-inputs">
          <div className="var-title">Input variables (Prompt Input / <code>--var</code>)</div>
          {local.inputs.map((inp, i) => (
            <div className="input-row" key={i}>
              <input placeholder="name" value={inp.name} onChange={(e) => setInput(i, "name", e.target.value)} />
              <input placeholder="label" value={inp.label || ""} onChange={(e) => setInput(i, "label", e.target.value)} />
              <input placeholder="default" value={inp.default || ""} onChange={(e) => setInput(i, "default", e.target.value)} />
              <button className="btn small danger" onClick={() => removeInput(i)}>✕</button>
            </div>
          ))}
          <button className="btn small" onClick={addInput}>+ Add input</button>
        </div>

        <div className="modal-actions">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={apply}>Apply</button>
        </div>
      </div>
    </div>
  );
}
