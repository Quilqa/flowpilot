# FlowPilot — Visual Desktop Automation Script Builder

Build, save, and run Windows desktop automation scripts as visual node graphs.
No code required. Flows are portable JSON files that run from the web UI, the
command line, or Windows Task Scheduler.

> Platform: **Windows 10/11, single monitor**. See PRD.md for the full spec.

---

## Quick start

### 1. Install backend dependencies

```powershell
python -m pip install -r requirements.txt
```

### 2. Build the frontend (one time, or after UI changes)

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 3. Run the server

```powershell
python server.py
```

Open **http://localhost:8321** in your browser.

> If you skip the build step the server still starts, but only the API is
> available — build the frontend to get the UI.

### Frontend dev mode (optional)

For live-reload UI development, run the API and Vite dev server side by side:

```powershell
python server.py            # terminal 1 (API on :8321)
cd frontend && npm run dev  # terminal 2 (UI on :5173, proxies to the API)
```

---

## Building a flow

1. **New Flow** on the home screen.
2. Drag nodes from the left palette onto the canvas (or click to add).
3. Drag from a node's right port to another node's left port to connect them.
   Condition nodes have two ports: **Yes** (green) / **No** (red).
4. Click a node to edit its parameters on the right.
5. `Ctrl+S` to save. The flow auto-saves every 30 seconds.

### Node types

| Group | Nodes |
|---|---|
| **Mouse** | Move, Down, Up, Click, Scroll |
| **Keyboard** | Key Down, Key Up, Key Press, Type Text, Shortcut (presets + custom combo) |
| **Flow** | Wait, Image Condition, Counter Condition, End |
| **Variables** | Set Variable, Copy to Variable, Paste Variable, Prompt Input |

### Coordinates & templates

- **XY picker** — click the crosshair on any coordinate field to pick a pixel
  from a live screenshot (with a zoom lens). Picking on a screenshot means the
  browser window never blocks the target.
- **Image Condition** — pick/capture a template PNG, set a confidence threshold
  (default 0.85), optional grayscale, and *check once* or *poll until timeout*.
  On a match it sets `match_x`, `match_y`, `match_confidence` so a following
  Mouse Move can target `{match_x}`, `{match_y}`.
- **Capture from screen** — countdown, then drag a rectangle to crop a template
  into `templates/<flow>/`.

### Variables

- All text/coordinate fields accept `{var_name}` interpolation.
- `Set Variable` supports arithmetic (`{a}+1`) and string concatenation.
- Comparisons auto-coerce to numbers when both sides parse as numbers.
- Declare flow inputs in **Settings** — they appear in the Run dialog and as
  `--var` CLI flags.

---

## Running flows

### From the UI

Open a flow, click **▶ Run**, fill any inputs, and start. A countdown lets you
focus the target app. The live log highlights the current node, shows variable
values, and reports condition confidence. Controls: **Pause / Resume / Stop**.

### From the CLI (headless)

```powershell
python runner.py flows/my_flow.json --var user=john --var count=5 [--log logs/custom.log] [--no-delay]
```

- Exit code `0` on success, non-zero on failure/abort (Task Scheduler friendly).
- A timestamped log is written to `logs/`.

### Windows Task Scheduler

On the home screen, use a flow's **CLI** button to copy the exact command and
working directory. In Task Scheduler:

- **Program/script**: the copied `python runner.py …` command.
- **Start in**: the copied working directory.
- **Run only when user is logged on** is *required* — GUI automation cannot run
  on a locked session.

---

## Safety

- **Panic hotkey `Ctrl+Alt+Esc`** aborts any run immediately (UI and headless).
- **pyautogui failsafe** — slam the mouse into a screen corner to abort. Toggle
  per flow in Settings.
- **Max run duration** guard (default 30 min, per-flow override).
- **Loop guard** — aborts after N iterations of the same node (default 10,000).

---

## Elevation (Administrator apps)

Windows UIPI prevents a normal-privilege process from sending input to a window
running as Administrator. If your target app is elevated, **run FlowPilot
elevated too** (start the server or `runner.py` from an Administrator terminal).
The runner logs a warning when input appears to be blocked.

## DPI scaling

Templates and coordinates are resolution/scale sensitive. Templates store the
DPI scale at capture time and the UI warns on a mismatch. For best results keep
Windows display scaling at **100%**, and identical between capture and run.

---

## Troubleshooting

**"WebSocket error" when starting a run** — uvicorn is installed without
WebSocket support. Fix:

```powershell
py -m pip install "uvicorn[standard]" websockets
```

**Key presses don't register in a game / Android emulator (MuMu, BlueStacks…)**
— keys are sent via Win32 `SendInput` with hardware scan codes, which these
apps accept. If a mapped key still doesn't trigger:
- Increase **Hold duration** on the Key Press node (games often need
  100–200 ms; the default is 80 ms).
- Make sure the emulator is the foreground window (start the flow with an
  Alt+Tab Shortcut node, or use the start-delay countdown to focus it).
- If the target runs as Administrator, run FlowPilot elevated too (see
  Elevation above).

**Template capture: how the countdown works** — click *Capture from screen*,
then during the countdown Alt+Tab to the target window. When the countdown
hits zero the server snapshots the screen; Alt+Tab back to the browser and
drag a rectangle on that snapshot. The crop is taken from the exact image you
see, so the browser never ends up in your template.

**Image Condition never matches** — check the run log in `logs/`: each
`condition_check` line records the measured confidence. If it is far below
your threshold, the usual causes are a DPI-scaling change since the template
was captured, or the target rendering at a different size.

---

## Project layout

```
flowpilot/
├─ flows/            # saved flows (one JSON per flow)
├─ templates/        # template PNGs, per-flow subfolders
├─ logs/             # run logs (one file per run)
├─ backend/          # FastAPI app + execution engine
├─ frontend/         # React + React Flow UI (built to frontend/dist)
├─ runner.py         # CLI runner
├─ server.py         # web UI server
├─ config.json       # global settings (port, defaults, hotkeys)
└─ requirements.txt
```

## Configuration (`config.json`)

| Key | Default | Purpose |
|---|---|---|
| `port` | 8321 | Server port |
| `default_confidence` | 0.85 | Image Condition default threshold |
| `default_poll_interval_ms` | 250 | Poll mode recheck interval |
| `default_poll_timeout_ms` | 5000 | Poll mode timeout |
| `start_delay_ms` | 3000 | Default run start countdown |
| `max_duration_ms` | 1800000 | Default max run duration (30 min) |
| `loop_guard_iterations` | 10000 | Same-node loop guard |
| `failsafe` | true | pyautogui corner-abort |
| `panic_hotkey` | `ctrl+alt+esc` | Global abort hotkey |
