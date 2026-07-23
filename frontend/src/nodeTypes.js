// Central registry describing every FlowPilot node type (PRD §4.2).
// Field types drive the parameter editor; `ports` drives edge handles.

// Field type reference:
//   text    - single-line string (supports {var})
//   textarea- multi-line string
//   number  - numeric input
//   select  - dropdown (options: [{value,label}])
//   checkbox- boolean
//   xy      - two number inputs (x/y) + crosshair picker
//   key     - key picker (dropdown + capture)
//   template- image template picker/capture
//   region  - screen rectangle picker

export const GROUPS = ["Mouse", "Keyboard", "Flow", "Screen", "Variables", "Functions"];

// Functions get their own hue: their nodes, palette group and the shaded area
// drawn behind each body all use it, so a function reads as a separate region
// of the canvas rather than part of the main path.
export const FUNCTION_COLOR = "#0d9488";

const BUTTONS = [
  { value: "left", label: "Left" },
  { value: "right", label: "Right" },
  { value: "middle", label: "Middle" },
];

export const NODE_DEFS = {
  start: { label: "Start", group: "Flow", color: "#16a34a", ports: "start", fields: [], system: true },
  end: {
    label: "End", group: "Flow", color: "#dc2626", ports: "in",
    fields: [{ key: "exit_code", type: "number", label: "Exit code", default: 0 }],
  },

  // --- Mouse ---
  mouse_move: {
    label: "Mouse Move", group: "Mouse", color: "#2563eb", ports: "linear",
    fields: [
      { key: "xy", type: "xy", label: "Target", xKey: "x", yKey: "y" },
      { key: "duration_ms", type: "number", label: "Transition (ms)", default: 0, hint: "0 = instant" },
      { key: "easing", type: "select", label: "Easing", default: "linear",
        options: [{ value: "linear", label: "Linear" }, { value: "ease-in-out", label: "Ease-in-out" }] },
    ],
  },
  mouse_down: {
    label: "Mouse Down", group: "Mouse", color: "#2563eb", ports: "linear",
    fields: [
      { key: "button", type: "select", label: "Button", options: BUTTONS, default: "left" },
      { key: "xy", type: "xy", label: "Position (optional)", xKey: "x", yKey: "y", optional: true },
    ],
  },
  mouse_up: {
    label: "Mouse Up", group: "Mouse", color: "#2563eb", ports: "linear",
    fields: [
      { key: "button", type: "select", label: "Button", options: BUTTONS, default: "left" },
      { key: "xy", type: "xy", label: "Position (optional)", xKey: "x", yKey: "y", optional: true },
    ],
  },
  mouse_click: {
    label: "Mouse Click", group: "Mouse", color: "#2563eb", ports: "linear",
    fields: [
      { key: "button", type: "select", label: "Button", options: BUTTONS, default: "left" },
      { key: "xy", type: "xy", label: "Position (optional)", xKey: "x", yKey: "y", optional: true },
      { key: "clicks", type: "number", label: "Click count", default: 1 },
      { key: "interval_ms", type: "number", label: "Interval between clicks (ms)", default: 0 },
    ],
  },
  mouse_scroll: {
    label: "Mouse Scroll", group: "Mouse", color: "#2563eb", ports: "linear",
    fields: [
      { key: "direction", type: "select", label: "Direction", default: "down",
        options: [{ value: "up", label: "Up" }, { value: "down", label: "Down" }] },
      { key: "amount", type: "number", label: "Amount", default: 3 },
    ],
  },

  // --- Keyboard ---
  key_down: { label: "Key Down", group: "Keyboard", color: "#7c3aed", ports: "linear",
    fields: [{ key: "key", type: "key", label: "Key" }] },
  key_up: { label: "Key Up", group: "Keyboard", color: "#7c3aed", ports: "linear",
    fields: [{ key: "key", type: "key", label: "Key" }] },
  key_press: { label: "Key Press", group: "Keyboard", color: "#7c3aed", ports: "linear",
    fields: [
      { key: "key", type: "key", label: "Key or combo", combo: true },
      { key: "hold_ms", type: "number", label: "Hold duration (ms)", default: 80,
        hint: "How long the key stays down. Games/emulators may need 100–200" },
    ] },
  type_text: {
    label: "Type Text", group: "Keyboard", color: "#7c3aed", ports: "linear",
    fields: [
      { key: "text", type: "textarea", label: "Text", hint: "Use {var} to insert variables" },
      { key: "delay_ms", type: "number", label: "Per-character delay (ms)", default: 0 },
    ],
  },
  shortcut: {
    label: "Shortcut", group: "Keyboard", color: "#7c3aed", ports: "linear",
    fields: [
      { key: "preset", type: "select", label: "Preset", default: "copy", options: [
        { value: "copy", label: "Copy (Ctrl+C)" }, { value: "paste", label: "Paste (Ctrl+V)" },
        { value: "cut", label: "Cut (Ctrl+X)" }, { value: "select_all", label: "Select All (Ctrl+A)" },
        { value: "save", label: "Save (Ctrl+S)" }, { value: "alt_tab", label: "Alt+Tab" },
        { value: "alt_shift_tab", label: "Alt+Shift+Tab" }, { value: "win_d", label: "Win+D" },
        { value: "enter", label: "Enter" }, { value: "esc", label: "Esc" },
        { value: "tab", label: "Tab" }, { value: "custom", label: "Custom combo…" },
      ] },
      { key: "custom_combo", type: "text", label: "Custom combo", hint: "e.g. ctrl+shift+s",
        showIf: (p) => p.preset === "custom" },
    ],
  },

  // --- Flow control ---
  wait: {
    label: "Wait", group: "Flow", color: "#ca8a04", ports: "linear",
    fields: [
      { key: "random", type: "checkbox", label: "Random range", default: false },
      { key: "duration_ms", type: "number", label: "Duration (ms)", default: 1000, showIf: (p) => !p.random },
      { key: "min_ms", type: "number", label: "Min (ms)", default: 500, showIf: (p) => p.random },
      { key: "max_ms", type: "number", label: "Max (ms)", default: 1500, showIf: (p) => p.random },
    ],
  },
  image_condition: {
    label: "Image Condition", group: "Flow", color: "#0891b2", ports: "condition",
    fields: [
      { key: "template", type: "template", label: "Template image" },
      { key: "region", type: "region", label: "Search region", hint: "Empty = full screen" },
      { key: "confidence", type: "slider", label: "Confidence", min: 0.5, max: 1.0, step: 0.01, default: 0.85 },
      { key: "grayscale", type: "checkbox", label: "Grayscale matching", default: true },
      { key: "mode", type: "select", label: "Check mode", default: "once", options: [
        { value: "once", label: "Check once" }, { value: "poll", label: "Poll until timeout" },
      ] },
      { key: "interval_ms", type: "number", label: "Poll interval (ms)", default: 250, showIf: (p) => p.mode === "poll" },
      { key: "timeout_ms", type: "number", label: "Timeout (ms)", default: 5000, showIf: (p) => p.mode === "poll" },
    ],
  },
  counter_condition: {
    label: "Counter Condition", group: "Flow", color: "#0891b2", ports: "condition",
    fields: [
      { key: "variable", type: "text", label: "Variable name", hint: "e.g. i" },
      { key: "operator", type: "select", label: "Operator", default: "<", options: [
        { value: "==", label: "==" }, { value: "!=", label: "!=" }, { value: ">", label: ">" },
        { value: "<", label: "<" }, { value: ">=", label: ">=" }, { value: "<=", label: "<=" },
        { value: "contains", label: "contains" },
      ] },
      { key: "value", type: "text", label: "Compare to", hint: "literal or {var}" },
    ],
  },

  // --- Screen ---
  screenshot: {
    label: "Screenshot", group: "Screen", color: "#7c3aed", ports: "linear",
    fields: [
      { key: "region", type: "region", label: "Region", hint: "Empty = whole screen" },
      { key: "filename", type: "text", label: "File name", default: "",
        hint: "Blank = auto (flow_runid_NNN). Tokens: {run_id} {n} {timestamp} {var}. Saved to screenshots/" },
      { key: "variable", type: "text", label: "Store path in", default: "screenshot_path",
        hint: "Variable holding the saved file path" },
    ],
  },

  // --- Functions ---
  // A function body is entered by calling it, never by an edge from Start, so
  // function_start has a source handle only — like Start itself.
  function_start: {
    label: "Function", group: "Functions", color: FUNCTION_COLOR, ports: "start",
    fields: [
      { key: "name", type: "text", label: "Function name", hint: "e.g. tap_ok — call it with a Call node" },
    ],
  },
  call_function: {
    label: "Call Function", group: "Functions", color: FUNCTION_COLOR, ports: "linear",
    fields: [
      { key: "name", type: "function", label: "Function", hint: "Runs the function, then continues here" },
    ],
  },
  function_return: {
    label: "Return", group: "Functions", color: FUNCTION_COLOR, ports: "in",
    fields: [],
  },

  // --- Variables & clipboard ---
  set_variable: {
    label: "Set Variable", group: "Variables", color: "#db2777", ports: "linear",
    fields: [
      { key: "name", type: "text", label: "Name" },
      { key: "value", type: "text", label: "Value / expression", hint: "e.g. {a}+1 or hello {name}" },
    ],
  },
  copy_to_variable: {
    label: "Copy to Variable", group: "Variables", color: "#db2777", ports: "linear",
    fields: [{ key: "name", type: "text", label: "Variable name", default: "copied_text" }],
  },
  paste_variable: {
    label: "Paste Variable", group: "Variables", color: "#db2777", ports: "linear",
    fields: [{ key: "name", type: "text", label: "Variable name", default: "copied_text" }],
  },
  prompt_input: {
    label: "Prompt Input", group: "Variables", color: "#db2777", ports: "linear",
    fields: [
      { key: "name", type: "text", label: "Input variable name" },
      { key: "label", type: "text", label: "Prompt label (optional)" },
    ],
  },
};

export function defaultParams(type) {
  const def = NODE_DEFS[type];
  if (!def) return {};
  const p = {};
  for (const f of def.fields) {
    if (f.type === "xy") continue; // xy fields leave x/y unset (use current pos)
    if (f.default !== undefined) p[f.key] = f.default;
  }
  return p;
}

export function isCondition(type) {
  return NODE_DEFS[type]?.ports === "condition";
}

export const PALETTE = GROUPS.map((g) => ({
  group: g,
  items: Object.entries(NODE_DEFS)
    .filter(([, d]) => d.group === g && !d.system && d.label !== "Start")
    .map(([type, d]) => ({ type, label: d.label, color: d.color })),
}));
