import { useState } from "react";
import { NODE_DEFS } from "../nodeTypes.js";
import ScreenPicker from "./ScreenPicker.jsx";
import KeyPicker from "./KeyPicker.jsx";
import TemplateField from "./TemplateField.jsx";

export default function ParamPanel({ node, flowName, onChange, onDelete, onClose }) {
  const type = node.data.nodeType;
  const def = NODE_DEFS[type];
  const params = node.data.params || {};
  const [picker, setPicker] = useState(null); // { mode:'point'|'region', field }

  const set = (key, value) => onChange({ ...params, [key]: value });
  const setMany = (obj) => onChange({ ...params, ...obj });

  if (!def) return null;

  return (
    <div className="param-panel">
      <div className="param-header" style={{ borderColor: def.color }}>
        <span>{def.label}</span>
        <button className="icon-btn" onClick={onClose} title="Close">✕</button>
      </div>
      <div className="param-body">
        <div className="field">
          <label className="muted">Node ID</label>
          <div className="mono small">{node.id}</div>
        </div>

        {def.fields.map((f) => {
          if (f.showIf && !f.showIf(params)) return null;
          return <Field key={f.key} f={f} params={params} set={set} setMany={setMany}
                        flowName={flowName} onPick={(mode) => setPicker({ mode, field: f })} />;
        })}

        {def.fields.length === 0 && <p className="muted">No parameters.</p>}
      </div>
      <div className="param-footer">
        {type !== "start" && <button className="btn small danger" onClick={onDelete}>Delete node</button>}
      </div>

      {picker && (
        <ScreenPicker
          mode={picker.mode}
          onCancel={() => setPicker(null)}
          onPick={(val) => {
            if (picker.mode === "point") {
              setMany({ [picker.field.xKey]: val.x, [picker.field.yKey]: val.y });
            } else {
              set(picker.field.key, val); // {left,top,width,height}
            }
            setPicker(null);
          }}
        />
      )}
    </div>
  );
}

function Field({ f, params, set, flowName, onPick }) {
  const val = params[f.key];

  switch (f.type) {
    case "text":
      return (
        <div className="field">
          <label>{f.label}</label>
          <input type="text" value={val ?? ""} placeholder={f.hint || ""}
                 onChange={(e) => set(f.key, e.target.value)} />
        </div>
      );
    case "textarea":
      return (
        <div className="field">
          <label>{f.label}</label>
          <textarea rows={3} value={val ?? ""} placeholder={f.hint || ""}
                    onChange={(e) => set(f.key, e.target.value)} />
        </div>
      );
    case "number":
      return (
        <div className="field">
          <label>{f.label}</label>
          <input type="number" value={val ?? f.default ?? 0}
                 onChange={(e) => set(f.key, e.target.value === "" ? "" : Number(e.target.value))} />
          {f.hint && <span className="hint">{f.hint}</span>}
        </div>
      );
    case "select":
      return (
        <div className="field">
          <label>{f.label}</label>
          <select value={val ?? f.default} onChange={(e) => set(f.key, e.target.value)}>
            {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      );
    case "checkbox":
      return (
        <div className="field checkbox-field">
          <label><input type="checkbox" checked={!!val} onChange={(e) => set(f.key, e.target.checked)} /> {f.label}</label>
        </div>
      );
    case "slider":
      return (
        <div className="field">
          <label>{f.label}: <b>{val ?? f.default}</b></label>
          <input type="range" min={f.min} max={f.max} step={f.step}
                 value={val ?? f.default} onChange={(e) => set(f.key, Number(e.target.value))} />
        </div>
      );
    case "xy":
      return (
        <div className="field">
          <label>{f.label}</label>
          <div className="xy-row">
            <input type="number" placeholder="X" value={params[f.xKey] ?? ""}
                   onChange={(e) => set(f.xKey, e.target.value === "" ? "" : Number(e.target.value))} />
            <input type="number" placeholder="Y" value={params[f.yKey] ?? ""}
                   onChange={(e) => set(f.yKey, e.target.value === "" ? "" : Number(e.target.value))} />
            <button className="btn small" title="Pick from screenshot" onClick={() => onPick("point")}>⊹ Pick</button>
          </div>
          {f.optional && <span className="hint">Leave empty to use current cursor position</span>}
        </div>
      );
    case "region":
      return (
        <div className="field">
          <label>{f.label}</label>
          <div className="xy-row">
            <span className="mono small">
              {val ? `${val.left},${val.top} ${val.width}×${val.height}` : "Full screen"}
            </span>
            <button className="btn small" onClick={() => onPick("region")}>▢ Select</button>
            {val && <button className="btn small" onClick={() => set(f.key, null)}>Clear</button>}
          </div>
          {f.hint && <span className="hint">{f.hint}</span>}
        </div>
      );
    case "key":
      return <KeyPicker label={f.label} combo={f.combo} value={val ?? ""} onChange={(v) => set(f.key, v)} />;
    case "template":
      return <TemplateField label={f.label} flowName={flowName} value={val ?? ""} onChange={(v) => set(f.key, v)} />;
    default:
      return null;
  }
}
