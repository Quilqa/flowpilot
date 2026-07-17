// Produce a short one-line summary of a node's params for the canvas.
export function nodeSummary(type, p = {}) {
  switch (type) {
    case "mouse_move":
      return `→ ${p.x ?? "?"},${p.y ?? "?"}${p.duration_ms ? ` (${p.duration_ms}ms)` : ""}`;
    case "mouse_click":
      return `${p.button || "left"}${p.clicks > 1 ? ` ×${p.clicks}` : ""}${p.x != null ? ` @${p.x},${p.y}` : ""}`;
    case "mouse_down":
    case "mouse_up":
      return `${p.button || "left"}${p.x != null ? ` @${p.x},${p.y}` : ""}`;
    case "mouse_scroll":
      return `${p.direction || "down"} ${p.amount ?? 3}`;
    case "key_down":
    case "key_up":
    case "key_press":
      return p.key || "—";
    case "type_text":
      return p.text ? `"${String(p.text).slice(0, 24)}"` : "—";
    case "shortcut":
      return p.preset === "custom" ? p.custom_combo || "custom" : p.preset || "—";
    case "wait":
      return p.random ? `${p.min_ms}–${p.max_ms}ms` : `${p.duration_ms ?? 0}ms`;
    case "image_condition":
      return `${(p.template || "").split("/").pop() || "no template"} @${p.confidence ?? 0.85}${p.mode === "poll" ? " (poll)" : ""}`;
    case "counter_condition":
      return `${p.variable || "?"} ${p.operator || "<"} ${p.value ?? "?"}`;
    case "set_variable":
      return `${p.name || "?"} = ${p.value ?? ""}`;
    case "copy_to_variable":
      return `→ ${p.name || "copied_text"}`;
    case "paste_variable":
      return `${p.name || "copied_text"} →`;
    case "prompt_input":
      return p.name || "—";
    case "end":
      return `exit ${p.exit_code ?? 0}`;
    default:
      return "";
  }
}
