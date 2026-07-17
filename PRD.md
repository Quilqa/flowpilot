# PRD — FlowPilot: Visual Desktop Automation Script Builder

**Version:** 1.0 · **Date:** 2026-07-06 · **Platform:** Windows 10/11, single monitor · **Status:** Draft for implementation

---

## 1. Overview

FlowPilot is a locally hosted web application (localhost server) for visually building, saving, and running desktop automation scripts on Windows. Users construct scripts as node graphs ("flows"): each node is a step (mouse action, keyboard action, wait, variable operation, or screenshot-based condition), and edges define execution order, including if/else branching and conditional loops.

Flows are stored as portable JSON files in the project folder. They can be executed three ways: from the web UI, from the command line (headless runner), or via Windows Task Scheduler.

### 1.1 Goals
- Build automation scripts with zero code, using a drag-and-drop graph editor.
- Robust screen-state detection via template image matching with configurable confidence and polling.
- One-click execution from the UI and unattended execution via CLI/Task Scheduler.

### 1.2 Non-goals (v1)
- Multi-monitor support, macOS/Linux support.
- Recording mode (record my actions → generate flow) — candidate for v2.
- OCR/text recognition on screen — candidate for v2.
- Remote execution or cloud sync.

---

## 2. Architecture

| Component | Technology | Rationale |
|---|---|---|
| Backend / runtime | **Python 3.11+** | Most stable, mature ecosystem for Windows GUI automation across arbitrary apps |
| Web server | FastAPI + Uvicorn (localhost, default port 8321) | Async, WebSocket support for live run logs |
| Frontend | React + React Flow (graph canvas) | React Flow is the standard for node-graph editors |
| Mouse/keyboard | `pyautogui` + `pywin32` (SendInput fallback) | pyautogui for high-level actions; SendInput for apps that ignore synthetic events (games, elevated windows) |
| Screen capture & matching | `mss` (capture) + `OpenCV` (`cv2.matchTemplate`, TM_CCOEFF_NORMED) | mss is the fastest Windows capture; OpenCV template matching supports confidence thresholds needed for animated/inconsistent backgrounds |
| Clipboard | `pyperclip` | Copy/paste variable support |
| Storage | JSON files on disk (no database) | Portable, human-readable, Task Scheduler friendly |

**Process model:** one Python process serves the UI and executes flows. The headless runner (`runner.py`) executes flows without starting the server.

**Elevation note:** if a target app runs as Administrator, the runner must also run elevated (Windows UIPI restriction). Documented in README; the runner logs a warning when input appears to be blocked.

---

## 3. Project folder layout

```
flowpilot/
├─ flows/                  # saved flows (one JSON per flow)
│   └─ my_flow.json
├─ templates/              # screenshot template images (PNG)
│   └─ my_flow/            # per-flow subfolder, auto-created
├─ logs/                   # run logs (one file per run)
├─ runner.py               # CLI runner: python runner.py flows/my_flow.json
├─ server.py               # web UI server: python server.py
└─ config.json             # global settings (port, default confidence, hotkeys)
```

Users may drop PNG files directly into `templates/` — the UI file picker lists them alongside in-app captures.

---

## 4. Flow model

### 4.1 Graph semantics
- A flow is a directed graph with exactly one **Start** node.
- Every action node has one input port and one output port (straight-line continuation).
- **Condition nodes** have two output ports: **Yes** / **No** (if/else).
- Edges may point to any earlier node → loops are formed by wiring a condition's output back to a previous step.
- Dead-end output = flow ends on that path. An explicit **End** node is available for clarity.
- Validation on save: exactly one Start, no orphan nodes, no action node with two outgoing edges.

### 4.2 Node types (v1 — complete list)

**Mouse**
| Node | Parameters |
|---|---|
| Mouse Move | target X, Y; transition time (ms, 0 = instant); easing (linear / ease-in-out) |
| Mouse Down | button (left/right/middle); optional X,Y (default: current position) |
| Mouse Up | button; optional X,Y |
| Mouse Click | button; optional X,Y; click count (1/2/3); interval between clicks |
| Mouse Scroll | direction, amount |

**Keyboard**
| Node | Parameters |
|---|---|
| Key Down | key (from key picker) |
| Key Up | key |
| Key Press | key or combo (down+up) |
| Type Text | literal text or variable reference (`{var_name}`); per-character delay (ms) |
| Shortcut (preset picker) | Copy (Ctrl+C), Paste (Ctrl+V), Cut, Alt+Tab, Alt+Shift+Tab, Win+D, Enter, Esc, Tab, custom combo builder |

Key picker: dropdown of all standard keys (letters, digits, F1–F24, modifiers, navigation, numpad) plus a "press a key to capture" mode.

**Flow control**
| Node | Parameters |
|---|---|
| Wait | duration (ms), fixed or random range (min–max) |
| Image Condition | see §5 |
| Counter Condition | variable comparison (==, !=, >, <, >=, <=, contains) → Yes/No outputs; used for "loop N times" |
| End | terminates flow; exit code (0 = success, custom for scheduler) |

**Variables & clipboard**
| Node | Parameters |
|---|---|
| Set Variable | name, value (literal or expression: `{a}+1`, string concat) |
| Copy to Variable | performs Ctrl+C, stores clipboard into named variable (default `copied_text`) |
| Paste Variable | writes variable to clipboard, performs Ctrl+V |
| Prompt Input | flow declares input variables; values are entered in the UI before run, or passed via CLI `--var name=value` |

### 4.3 Variables
- String type in v1; numeric comparison auto-coerces when both sides parse as numbers.
- Any text/coordinate field accepts `{var_name}` interpolation (e.g. Mouse Move X = `{found_x}`).
- Declared flow inputs appear as a form in the "Run" dialog and as `--var` CLI flags.

---

## 5. Image Condition node (core feature)

**Question answered:** "Does this template image currently exist on the screen?"

Parameters:
- **Template**: pick from `templates/<flow>/`, upload a PNG, or **Capture from screen** (see §6.3).
- **Search region**: full screen (default) or a rectangle (picked visually, same overlay as §6.2). Restricting the region speeds matching and avoids false positives.
- **Confidence threshold**: 0.50–1.00 slider, default **0.85**. Lower values tolerate animated backgrounds, anti-aliasing, and slight rendering differences.
- **Grayscale matching**: on/off (on = more tolerant of color shifts, faster).
- **Check mode** (configurable per step):
  - *Check once* — single capture, branch immediately.
  - *Poll until timeout* — recheck every *interval* ms (default 250) up to *timeout* ms (default 5000). Yes fires as soon as a match is found; No fires on timeout.
- **Outputs**: Yes / No branches.
- **Side effects**: on match, sets `match_x`, `match_y` (center of found template) and `match_confidence` variables — enables "find the button, then click where it was found" via Mouse Move to `{match_x}`,`{match_y}`.

Matching implementation: `cv2.matchTemplate` with `TM_CCOEFF_NORMED`; match = max value ≥ threshold. Screen captured at native resolution; templates must be captured at the same display scale (UI warns if Windows DPI scaling changed since template capture — scale factor stored in template metadata).

---

## 6. Web UI

### 6.1 Screens
1. **Flow list (home)** — dropdown/list of all flows in `flows/`; per-flow actions: Run, Edit, Duplicate, Rename, Delete, Show CLI command (for Task Scheduler).
2. **Graph editor** — React Flow canvas: node palette (grouped: Mouse / Keyboard / Flow / Variables), drag to add, click node to open parameter panel, drag between ports to connect, Yes/No ports color-coded (green/red). Pan/zoom, undo/redo, Ctrl+S save, auto-save every 30 s.
3. **Run view** — live log via WebSocket: current node highlighted on the canvas, per-step status, variable values, condition results with measured confidence. Controls: **Stop**, **Pause/Resume**. Global panic hotkey **Ctrl+Alt+Esc** aborts any run (works headless too).

### 6.2 XY position picker
For any coordinate field: click the crosshair icon → the server takes a full-screen screenshot → shown in a full-window overlay in the browser → user clicks the exact pixel → coordinates fill in. Zoom lens (magnified area around cursor) for pixel-accurate picking. Live coordinate readout while hovering.

Rationale: picking on a *screenshot* (not live screen) means the browser window itself never obstructs the target.

### 6.3 In-app template capture
"Capture from screen" in the Image Condition panel:
1. Optional countdown (0–10 s) so the user can bring the target window forward.
2. Server captures the screen; overlay lets the user drag a rectangle.
3. Cropped PNG saved to `templates/<flow>/` with an auto or user-supplied name; DPI scale stored in metadata.

### 6.4 Run start delay
Runs from the UI begin after a configurable countdown (default 3 s) so the browser can be minimized / target app focused. An optional first "Alt+Tab" or "Focus window by title" preset covers the common case.

---

## 7. Execution & scheduling

### 7.1 UI execution
Flow list → pick flow → fill input variables → Run. Live log as in §6.1.

### 7.2 CLI runner
```
python runner.py flows/my_flow.json --var user=john --var count=5 [--log logs/custom.log]
```
- Exit code 0 on success, non-zero on failure/abort (Task Scheduler compatible).
- Writes timestamped log to `logs/`.

### 7.3 Task Scheduler
The UI's "Show CLI command" produces the exact command + working directory to paste into a scheduled task. README documents: "Run only when user is logged on" is required (GUI automation cannot run on a locked session — documented limitation).

### 7.4 Safety
- Panic hotkey Ctrl+Alt+Esc (global, registered by runner) — immediate abort.
- pyautogui failsafe (mouse to top-left corner aborts) enabled by default, toggle in config.
- Max run duration guard (default 30 min, per-flow override).
- Loop guard: warn/abort after N iterations of the same cycle without an intervening Wait (default 10,000).

---

## 8. Flow file format (JSON)

```json
{
  "name": "invoice_download",
  "version": 1,
  "inputs": [{"name": "invoice_id", "default": ""}],
  "settings": {"start_delay_ms": 3000, "max_duration_ms": 1800000},
  "nodes": [
    {"id": "n1", "type": "start"},
    {"id": "n2", "type": "image_condition",
     "params": {"template": "templates/invoice_download/login_btn.png",
                "confidence": 0.85, "mode": "poll", "timeout_ms": 5000,
                "interval_ms": 250, "region": null, "grayscale": true}},
    {"id": "n3", "type": "mouse_move", "params": {"x": 1130, "y": 1055, "duration_ms": 300}},
    {"id": "n4", "type": "mouse_click", "params": {"button": "left"}}
  ],
  "edges": [
    {"from": "n1", "to": "n2"},
    {"from": "n2", "to": "n3", "port": "yes"},
    {"from": "n2", "to": "n7", "port": "no"},
    {"from": "n3", "to": "n4"}
  ]
}
```

---

## 9. Acceptance criteria (v1)

1. User can build, save, reopen, and edit a flow containing every node type in §4.2.
2. XY picker fills coordinates from a screenshot click with pixel accuracy.
3. Template capture crops and saves a PNG usable by an Image Condition.
4. Image Condition branches correctly at ≥0.85 confidence on a static UI and, with lowered confidence, on a target over an animated background; poll mode respects interval and timeout.
5. If/else example from the brief works end-to-end: template found → move to [1130,1055], click, move to [560,884], click; not found → alternate branch executes.
6. Loop: a Counter Condition wired back to an earlier node repeats exactly N times.
7. Copy to Variable captures selected text; Type Text / Paste Variable reproduces it in another app; Alt+Tab preset switches windows.
8. `runner.py` executes a saved flow headlessly with `--var` inputs and returns correct exit codes; a Windows Task Scheduler task using the generated command runs successfully.
9. Panic hotkey aborts a running flow within 500 ms.

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| DPI scaling changes break templates/coordinates | Store scale in metadata; warn on mismatch; recommend 100% scaling |
| Target app ignores synthetic input | SendInput backend fallback; document elevation requirement |
| False positives on animated UIs | Region restriction + grayscale + tunable confidence + poll mode |
| Runaway loops clicking wildly | Loop guard, max duration, failsafe corner, panic hotkey |

## 11. v2 candidates
Action recorder, OCR text conditions, multi-monitor, sub-flows (call flow from flow), try/retry wrapper node, image "wait until disappears" mode, flow import/export bundles (flow + templates zip).
