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

### Functions (reusable named sub-flows)

For a sequence you use repeatedly, define it **once** as a function instead of
pasting copies — fix the function and every call site changes with it.

1. Drag a **Function** node onto an empty part of the canvas and give it a
   name (e.g. `tap_ok`). Build the body after it, ending with **Return**.
2. Anywhere in the flow, drop a **Call Function** node and pick the name from
   the dropdown. Execution jumps into the function and comes back to the node
   after the call.

The body is drawn inside a shaded, labelled area so it reads as its own region
of the canvas — a function is entered by *calling* it, so it is deliberately
not wired to Start.

- **Variables are shared**, not local. Set a variable before the call and the
  function can read it; changes it makes are visible afterwards. That is how
  you pass arguments and return results.
- Functions may call other functions. Recursion is allowed but capped at 64
  levels, which aborts the run rather than exhausting memory.
- A body that simply runs out of nodes returns just like an explicit **Return**.
- An **End** node inside a function ends the *whole run*, not just the call.
- Functions are stored in the flow's own JSON, so a flow stays self-contained
  and still runs from `runner.py` and Task Scheduler.

### Reusing blocks (copy / paste)

Select nodes and copy them **with the connections between them**, so a
multi-node construct (a counter loop, an alt-tab scan) can be rebuilt in one
paste instead of by hand.

| Key | Action |
|---|---|
| `Shift`+drag | Box-select several nodes (`Ctrl`+click toggles one) |
| `Ctrl+C` | Copy the selection |
| `Ctrl+V` | Paste — new ids, offset slightly, pasted nodes become the selection |
| `Ctrl+D` | Duplicate the selection in place |

- Only edges with **both** ends inside the selection are copied; an edge
  leaving the selection would have nowhere to land.
- The **Start** node is never copied (a flow may only have one).
- The payload is JSON on the system clipboard, so it survives **across flows**
  and browser tabs — copy a loop out of one flow and paste it into another.
  You can also paste it into a text file to keep a snippet library.
- Pasted nodes arrive unconnected to the rest of the graph; wire them in by
  dragging from a port. Until then they show as *orphan* warnings on save.
- Copy/paste inside a parameter text field behaves normally (text, not nodes).

### Node types

| Group | Nodes |
|---|---|
| **Mouse** | Move, Down, Up, Click, Scroll |
| **Keyboard** | Key Down, Key Up, Key Press, Type Text, Shortcut (presets + custom combo) |
| **Flow** | Wait, Image Condition, Counter Condition, End |
| **Screen** | Screenshot |
| **Variables** | Set Variable, Copy to Variable, Paste Variable, Prompt Input |
| **Functions** | Function, Call Function, Return |

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

### Screenshot node

Saves a PNG of the screen (or a region) into `screenshots/` while the flow
runs — useful for recording what a flow saw at a given step.

- **Region** — empty captures the whole screen; otherwise use the rectangle
  picker, same as Image Condition.
- **File name** — blank auto-names it `<flow>_<timestamp>.png`. You may use
  `{timestamp}` and any flow variable, e.g. `login_{i}_{timestamp}`.
  A fixed name overwrites on each pass; include `{timestamp}` or a loop
  counter such as `{i}` to keep every iteration. The timestamp carries
  milliseconds, so a tight loop still produces distinct files.
- **Store path in** — the variable receiving the saved path (default
  `screenshot_path`), so a later node can reference `{screenshot_path}`.

File names are flattened to stay inside `screenshots/` — a name containing
path separators cannot write elsewhere.

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

**Type Text produced only digits and dots (letters missing or wrong)** — fixed.
Text is now sent as Unicode characters via `SendInput`, which ignores the
keyboard layout entirely. Previously it pressed *virtual keys* as if the US
layout were active, so with a non-Latin layout selected (Russian, Ukrainian,
Greek…) Windows mapped those key positions through that layout and letters
came out wrong, while digits and `.` — which sit on the same keys in both
layouts — appeared to work.

> Note the deliberate split: **Type Text** sends characters (layout
> independent, correct for text fields), while **Key Press / Key Down / Key Up
> / Shortcut** send *key positions* via scan codes — which is what games and
> emulator key-mappers need. So a Key Press of `a` under a Russian layout
> types `ф` in a text box; use Type Text for text.

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
├─ screenshots/      # PNGs saved by Screenshot nodes
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
