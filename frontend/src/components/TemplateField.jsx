import { useEffect, useState, useCallback } from "react";
import { api } from "../api.js";
import ScreenPicker from "./ScreenPicker.jsx";

export default function TemplateField({ label, flowName, value, onChange }) {
  const [templates, setTemplates] = useState([]);
  const [countdown, setCountdown] = useState(null);
  const [capturing, setCapturing] = useState(false);
  const [dpiWarn, setDpiWarn] = useState("");

  const refresh = useCallback(async () => {
    try { setTemplates(await api.listTemplates(flowName)); } catch {}
  }, [flowName]);

  useEffect(() => { refresh(); }, [refresh]);

  const startCapture = () => {
    let secs = 3;
    setCountdown(secs);
    const t = setInterval(() => {
      secs -= 1;
      if (secs <= 0) { clearInterval(t); setCountdown(null); setCapturing(true); }
      else setCountdown(secs);
    }, 1000);
  };

  const onRegion = async (region) => {
    setCapturing(false);
    const name = prompt("Template name:", `template_${Date.now().toString().slice(-5)}`);
    if (!name) return;
    try {
      const res = await api.captureTemplate(flowName, { ...region, name });
      await refresh();
      onChange(res.path);
      if (res.dpi_scale && res.dpi_scale !== 1.0)
        setDpiWarn(`Captured at DPI scale ${res.dpi_scale}× — keep Windows scaling identical at run time.`);
    } catch (e) { alert(`Capture failed: ${e.message}`); }
  };

  return (
    <div className="field">
      <label>{label}</label>
      <select value={value || ""} onChange={(e) => onChange(e.target.value)}>
        <option value="">— none —</option>
        {templates.map((t) => <option key={t.path} value={t.path}>{t.name}</option>)}
      </select>
      <div className="xy-row" style={{ marginTop: 6 }}>
        <button className="btn small primary" onClick={startCapture}>⛶ Capture from screen</button>
        <button className="btn small" onClick={refresh}>↻ Refresh</button>
      </div>
      {value && (
        <div className="template-preview">
          <img src={api.templateImageUrl(value)} alt="template" />
        </div>
      )}
      {dpiWarn && <span className="hint warn">{dpiWarn}</span>}

      {countdown !== null && (
        <div className="countdown-overlay"><div className="countdown-num">{countdown}</div>
          <div className="muted">Bring the target window forward…</div></div>
      )}
      {capturing && <ScreenPicker mode="region" onPick={onRegion} onCancel={() => setCapturing(false)} />}
    </div>
  );
}
