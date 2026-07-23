# FlowPilot — working notes for Claude Code

Visual builder for Windows desktop automation. Flows are JSON node graphs, run
from a React UI, the CLI, or Task Scheduler. `README.md` is the user-facing
doc; this file is the stuff that costs time to rediscover.

## Layout

```
server.py        web UI entry point (uvicorn + panic hotkey)
runner.py        headless CLI runner
backend/
  models.py      Flow/Node/Edge pydantic models + validate_flow()  ← NODE_TYPES lives here
  engine.py      FlowRunner: graph traversal, variables, one _execute() per node type
  automation.py  mouse/keyboard/clipboard wrappers (pyautogui + sendinput + mouseinput)
  sendinput.py   Win32 SendInput: scan codes (key positions) + Unicode (characters)
  mouseinput.py  Win32 mouse_event: absolute moves + button holds for drags
  capture.py     mss screen capture, DPI awareness, dpi_report()
  matching.py    OpenCV template matching
  runmanager.py  singleton driving the one active UI run + per-run logfile
  server.py      FastAPI routes + WebSocket run stream
  storage.py     flow file IO
frontend/src/
  nodeTypes.js   NODE_DEFS registry — drives palette, param editor, ports
  summary.js     one-line node summary shown on the canvas
  clipboard.js   copy/paste of node sub-graphs
  functions.js   derives the shaded function-area backdrops from nodes+edges
  components/Editor.jsx      React Flow canvas, save/autosave, undo/redo, shortcuts
  components/FunctionArea.jsx  function backdrop + ƒ-title drag handle
```

## Running it

```powershell
python server.py                       # foreground, console
wscript start_silent.vbs               # windowless; stop with stop_silent.vbs
cd frontend && npm run build           # required after ANY frontend edit
cd frontend && npm run dev             # :5173, proxies /api and /ws to :8321
```

- **The frontend is served from `frontend/dist/`.** Editing `frontend/src` does
  nothing until you `npm run build`. A browser refresh then picks it up.
- **Backend edits need a server restart** — the running process holds the old
  modules. Use `stop_silent.vbs` then `start_silent.vbs`.
- The user typically keeps the silent server running. Check before starting your
  own: `Get-NetTCPConnection -LocalPort 8321 -State Listen`.

## Adding a node type

Six places, and validation fails loudly if you miss the first:

1. `backend/models.py` → add the id to `NODE_TYPES` (and `CONDITION_TYPES` if it
   branches yes/no).
2. `backend/engine.py` → a branch in `_execute()`. Return
   `(port, result)`; action nodes return `(None, None)`, conditions return
   `("yes"|"no", None)`. Use `self._p/_int/_opt_int` so params get `{var}`
   interpolation.
3. `frontend/src/nodeTypes.js` → an entry in `NODE_DEFS`. `ports` is
   `linear` | `condition` | `in` | `start`. Field types: text, textarea, number,
   select, checkbox, xy, key, template, region, function. Add the group to
   `GROUPS` if new.
4. `frontend/src/summary.js` → a `case` for the canvas one-liner.
5. `frontend/src/components/RunView.jsx` → a `case` if the node emits a custom
   event (the switch ignores unknown types silently).
6. `README.md` node table, then `npm run build`.

## Gotchas that have bitten before

- **Autosave persists your experiments.** The editor autosaves every 30 s when
  dirty. Adding a test node to a real flow *will* be written to `flows/*.json`.
  Delete test nodes promptly, or work on a throwaway flow.
- **Flows and templates are gitignored** (`flows/*` except `demo_ifelse.json`
  and `standard_functions.json`, `templates/*`, `screenshots/*`, `logs/*.log`).
  They are personal user data; don't force-add without asking.
  `standard_functions.json` is a tracked library of reusable functions
  (drag_and_drop, alt_tab_to) that flows copy/paste from.
- **`pythonw` has no stdout.** `server.py` prints at startup, so running it under
  `pythonw` without redirecting output kills the process instantly and silently.
  `start_silent.vbs` redirects to `logs/server_silent.log` — keep that.
- **Typing vs key pressing.** `type_text` sends *characters* (SendInput
  `KEYEVENTF_UNICODE`) and is layout-independent. `key_press`/`key_down`/`key_up`
  /`shortcut` send *key positions* (scan codes), which is what emulators and
  games need — but under a non-Latin layout a Key Press of `a` types `ф`. Don't
  "unify" these; the split is deliberate.
- **Plain moves position with `SetCursorPos`; only held-button drags use
  `mouse_event`.** `automation._held_buttons` tracks button state so `mouse_move`
  can tell them apart. This matters for precision: `SetCursorPos` takes pixels
  directly in the screenshot's space (what the XY picker uses), so a picked
  pixel is hit exactly under any DPI scale. Normalizing through `mouse_event`'s
  0..65535 absolute space (what an earlier version did for *all* moves) depends
  on `GetSystemMetrics` matching the mss screenshot, which diverges under
  fractional scaling / monitor changes and made the picker miss. Drags still
  need `mouse_event` because emulators ignore `SetCursorPos`-only motion —
  `mouseinput.move_to` does `SetCursorPos` (precise) **plus** a raw absolute
  MOVE (recognition). `automation.reset_button_state()` is called at run start
  so a drag aborted mid-way doesn't leave a phantom held button.
- **DPI: use Per-Monitor-Aware-v2.** `capture.set_dpi_awareness()` prefers
  `SetProcessDpiAwarenessContext(-4)`; under v1 the legacy metrics can report
  scaled pixels on a monitor change. `/api/screen-size` returns `capture.dpi_report()`
  — if `consistent` is false, the screenshot space and cursor space disagree,
  which is the root cause of a picker that misses.
- **Every run writes `logs/<flow>_<run_id>.log`** (UI runs via
  `runmanager.py`, CLI via `runner.py`) — one JSON event per line. Per-node
  detail comes from `FlowRunner._describe()`, which interpolates params so the
  log shows real values; keep it in the engine, not the frontend summary.
- **`run_id` ties a run's artifacts together.** The caller passes the same
  stamp it uses for the log filename into `FlowRunner(run_id=...)`; auto-named
  screenshots become `<flow>_<run_id>_<NNN>.png`, sharing the log's prefix.
  Screenshot names also accept `{run_id}`/`{n}`/`{timestamp}` tokens, resolved
  in `_do_screenshot` (not from the variable map). `FlowRunner` generates a
  run_id when run standalone, so tests don't have to.
- **Held keys leak on abort.** Panic/Stop raises `RunAborted` and unwinds without
  releasing keys, so aborting between `Key Down alt` and `Key Up alt` leaves Alt
  stuck. Tap the key to clear.
- **The loop guard resets on `wait`.** `_loop_counter` is cleared whenever a Wait
  node runs, so deliberately paced loops don't trip it. Loops are made by
  pointing an edge backwards — there is no loop node.
- **Functions are graph-native, not a separate section.** A `function_start`
  node names the function; its body is whatever is reachable from it. The
  engine keeps a call stack (`_call_stack`) and `MAX_CALL_DEPTH` guards
  recursion. Entering a function is handled in the `run()` traversal loop, not
  in `_execute()` — a dead end inside a body returns to the caller instead of
  ending the run. Variables are global; there is no local scope.
- **Function backdrops are derived, never state.** `functions.js` computes the
  shaded areas from nodes+edges and `Editor.jsx` prepends them only to what it
  hands React Flow. They must stay out of `nodes` state or they would be
  selected, copied, and written into the flow file. Their ids are prefixed
  `__farea_`. Dragging the ƒ title translates the body: `FunctionArea` handles
  pointer events itself (the area is `draggable:false`) and converts the screen
  delta to flow space via the live zoom, moving the area's `memberIds`. The
  handle carries React Flow's `nopan` class — without it, `stopPropagation`
  isn't enough and the canvas pans along with the body (RF's pan is a d3-zoom
  listener on an ancestor, not a bubbling React handler).
- **Undo/redo is a debounced snapshot of nodes+edges** (`Editor.jsx`). Rapid
  changes — a drag's position stream, typing in a param field — coalesce into
  one step (~350 ms). Restores set a `restoring` guard so the commit effect
  doesn't record the restore itself. History is per editor session, not saved.
- **New nodes are placed in flow coordinates, via the RF instance.** Drop and
  click-to-add map through `rfRef.current.screenToFlowPosition(...)` (captured
  in `onInit`) — a drop uses the cursor point, click-to-add uses the visible
  canvas centre. Using raw screen pixels (an earlier bug) only lines up at pan
  (0,0) zoom 1; once panned/zoomed, nodes missed the cursor or landed off-screen
  near the origin.
- **Coordinates are DPI-sensitive.** `capture.set_dpi_awareness()` runs once at
  startup, before any capture or mouse move; changing it mid-process shifts the
  coordinate space.
- **Python here is x64 on an ARM64 machine** (runs under emulation). Don't repin
  `requirements.txt` to ARM64 wheels — `opencv-python` 4.10 and `pywin32` 308
  have no win_arm64 builds.

## Testing

GUI automation is awkward to test directly. What works:

- **Engine logic without real input:** monkeypatch `engine.automation` with a
  recorder and stub `FlowRunner._do_image_condition` / `_sleep`. Lets you assert
  the exact key sequence a loop produces.
- **Structure:** `validate_flow(Flow.model_validate(json))` — returns errors and
  warnings; run it after generating any flow JSON.
- **Real input:** create a focused window and read back what arrived. For
  layout-sensitive work, a raw `RegisterClassW` window recording `WM_CHAR` is
  ground truth — a Tk `Entry` mangles non-ASCII through the ANSI codepage and
  will lie to you.
- **Frontend logic:** run `npm run dev` and `await import('/src/foo.js')` from
  the browser console to exercise real modules without a test harness.

### Preview-browser caveat

In the in-app preview browser, `ResizeObserver` never fires, so **React Flow
renders no edges at all** and screenshots often time out. Nodes and the DOM are
fine. Don't chase this as a bug — verify edges via saved JSON or React state
instead. Multi-select via synthetic mouse events also doesn't work there.

## Conventions

- Comments explain *why*, not what; match the surrounding density.
- Engine node handlers stay small — push real work into `automation`/`capture`
  /`matching`.
- User-supplied strings that become file names go through
  `config.safe_filename()` (they may contain interpolated variables).
- Keep `git commit` to when asked. Flows/templates stay out of commits.
