import { useEffect, useState } from "react";

// Standard key list for the dropdown.
const LETTERS = "abcdefghijklmnopqrstuvwxyz".split("");
const DIGITS = "0123456789".split("");
const FKEYS = Array.from({ length: 24 }, (_, i) => `f${i + 1}`);
const MODIFIERS = ["ctrl", "alt", "shift", "win"];
const NAV = ["enter", "esc", "tab", "space", "backspace", "delete", "insert", "home", "end",
  "pageup", "pagedown", "up", "down", "left", "right", "capslock", "printscreen"];
const NUMPAD = ["num0", "num1", "num2", "num3", "num4", "num5", "num6", "num7", "num8", "num9",
  "add", "subtract", "multiply", "divide", "decimal"];

const ALL_KEYS = [...LETTERS, ...DIGITS, ...FKEYS, ...MODIFIERS, ...NAV, ...NUMPAD];

// Map browser KeyboardEvent to a pyautogui-friendly key name.
function eventToKey(e) {
  const k = e.key;
  const map = {
    " ": "space", Escape: "esc", ArrowUp: "up", ArrowDown: "down",
    ArrowLeft: "left", ArrowRight: "right", Control: "ctrl", Meta: "win",
  };
  if (map[k]) return map[k];
  if (k.length === 1) return k.toLowerCase();
  return k.toLowerCase();
}

export default function KeyPicker({ label, combo, value, onChange }) {
  const [capturing, setCapturing] = useState(false);

  useEffect(() => {
    if (!capturing) return;
    const onKey = (e) => {
      e.preventDefault();
      const parts = [];
      if (combo) {
        if (e.ctrlKey) parts.push("ctrl");
        if (e.altKey) parts.push("alt");
        if (e.shiftKey) parts.push("shift");
        if (e.metaKey) parts.push("win");
      }
      const base = eventToKey(e);
      if (!["ctrl", "alt", "shift", "win"].includes(base) || !combo) parts.push(base);
      onChange(combo ? [...new Set(parts)].join("+") : base);
      setCapturing(false);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [capturing, combo, onChange]);

  return (
    <div className="field">
      <label>{label}</label>
      <div className="xy-row">
        {combo ? (
          <input type="text" value={value} placeholder="e.g. ctrl+shift+s"
                 onChange={(e) => onChange(e.target.value)} />
        ) : (
          <select value={value} onChange={(e) => onChange(e.target.value)}>
            <option value="">— select —</option>
            {ALL_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        )}
        <button className={`btn small ${capturing ? "capturing" : ""}`}
                onClick={() => setCapturing((c) => !c)}>
          {capturing ? "Press a key…" : "⌨ Capture"}
        </button>
      </div>
    </div>
  );
}
