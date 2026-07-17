// Thin fetch wrapper around the FlowPilot backend REST API.

async function j(method, url, body) {
  // X-FlowPilot marks same-origin UI requests; the server rejects /api calls
  // without it, which (with restricted CORS) blocks cross-origin/CSRF access.
  const opts = { method, headers: { "X-FlowPilot": "1" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

export const api = {
  getConfig: () => j("GET", "/api/config"),
  listFlows: () => j("GET", "/api/flows"),
  getFlow: (name) => j("GET", `/api/flows/${encodeURIComponent(name)}`),
  saveFlow: (flow) => j("POST", "/api/flows", flow),
  validateFlow: (name, flow) => j("POST", `/api/flows/${encodeURIComponent(name)}/validate`, flow),
  deleteFlow: (name) => j("DELETE", `/api/flows/${encodeURIComponent(name)}`),
  duplicateFlow: (name, newName) => j("POST", `/api/flows/${encodeURIComponent(name)}/duplicate`, { new_name: newName }),
  renameFlow: (name, newName) => j("POST", `/api/flows/${encodeURIComponent(name)}/rename`, { new_name: newName }),
  cliCommand: (name) => j("GET", `/api/flows/${encodeURIComponent(name)}/cli`),

  screenSize: () => j("GET", "/api/screen-size"),
  screenshotUrl: () => `/api/screenshot?t=${Date.now()}`,

  listTemplates: (flow) => j("GET", `/api/templates/${encodeURIComponent(flow)}`),
  templateImageUrl: (path) => `/api/template-image?path=${encodeURIComponent(path)}&t=${Date.now()}`,
  captureTemplate: (flow, region) => j("POST", `/api/templates/${encodeURIComponent(flow)}/capture`, region),

  run: (name, variables) => j("POST", `/api/run/${encodeURIComponent(name)}`, { variables }),
  runControl: (action) => j("POST", `/api/run/control/${action}`),
  runStatus: () => j("GET", "/api/run/status"),
};

export function runSocket() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${proto}://${location.host}/ws/run`);
}
