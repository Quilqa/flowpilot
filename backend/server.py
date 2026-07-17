"""FastAPI application: flow CRUD, screenshots, template capture, run WebSocket."""
from __future__ import annotations

import asyncio
import queue
import threading
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import capture, config, storage
from .models import Flow, validate_flow
from .runmanager import manager

app = FastAPI(title="FlowPilot", version="1.0.0")

# The API drives the real mouse/keyboard and can screenshot the screen, so it
# must not be reachable by arbitrary web pages the user visits. Two guards:
#   1. CORS is limited to the local UI origins (blocks cross-origin *reads*).
#   2. Every /api request must carry the custom X-FlowPilot header. Custom
#      headers force a CORS preflight, which the restricted policy denies for
#      any other origin — so a malicious site can neither read responses nor
#      fire state-changing requests (e.g. /api/run). Same-origin UI requests
#      are exempt from CORS and simply include the header.
_cfg = config.load_config()
_port = int(_cfg.get("port", 8321))
ALLOWED_ORIGINS = [
    f"http://localhost:{_port}", f"http://127.0.0.1:{_port}",
    "http://localhost:5173", "http://127.0.0.1:5173",  # Vite dev server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# GET endpoints consumed via <img src>, which cannot send custom headers.
# They stay exempt from the header gate but are still protected from
# cross-origin *reading* by restricted CORS + HTML canvas cross-origin taint.
_HEADER_EXEMPT = {"/api/screenshot", "/api/template-image"}


@app.middleware("http")
async def require_client_header(request: Request, call_next):
    """Gate /api routes behind the X-FlowPilot header (CSRF protection)."""
    path = request.url.path
    if path.startswith("/api/") and path not in _HEADER_EXEMPT:
        if request.headers.get("x-flowpilot") != "1":
            return JSONResponse({"detail": "Missing X-FlowPilot header"}, status_code=403)
    return await call_next(request)


config.ensure_dirs()


# --- Config ----------------------------------------------------------------

@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return config.load_config()


# --- Flow CRUD -------------------------------------------------------------

@app.get("/api/flows")
def api_list_flows() -> list[dict[str, Any]]:
    return storage.list_flows()


@app.get("/api/flows/{name}")
def api_get_flow(name: str) -> dict[str, Any]:
    try:
        return storage.load_flow(name).to_json_dict()
    except FileNotFoundError:
        raise HTTPException(404, f"Flow '{name}' not found")


@app.post("/api/flows")
def api_save_flow(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    flow = Flow.model_validate(payload)
    issues = validate_flow(flow)
    storage.save_flow(flow)
    return {"ok": True, "name": flow.name, "issues": [i.model_dump() for i in issues]}


@app.post("/api/flows/{name}/validate")
def api_validate_flow(name: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    flow = Flow.model_validate(payload)
    issues = validate_flow(flow)
    return {"issues": [i.model_dump() for i in issues]}


@app.delete("/api/flows/{name}")
def api_delete_flow(name: str) -> dict[str, Any]:
    storage.delete_flow(name)
    return {"ok": True}


@app.post("/api/flows/{name}/duplicate")
def api_duplicate_flow(name: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    flow = storage.duplicate_flow(name, payload.get("new_name"))
    return {"ok": True, "name": flow.name}


@app.post("/api/flows/{name}/rename")
def api_rename_flow(name: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    new = payload.get("new_name")
    if not new:
        raise HTTPException(400, "new_name required")
    flow = storage.rename_flow(name, new)
    return {"ok": True, "name": flow.name}


@app.get("/api/flows/{name}/cli")
def api_cli_command(name: str) -> dict[str, Any]:
    """Produce the CLI command for Task Scheduler (PRD §7.3)."""
    p = config.flow_path(name)
    cwd = str(config.ROOT)
    cmd = f'python "{config.ROOT / "runner.py"}" "flows/{p.name}"'
    return {"command": cmd, "cwd": cwd}


# --- Screenshots & XY picker ----------------------------------------------

# The most recent full-screen capture served to the overlay. Template capture
# must crop from *this exact image* — the one the user dragged a rectangle on —
# not from a fresh capture taken later, when the browser (showing the overlay)
# is back in the foreground and would be what gets cropped.
_last_shot: dict[str, Any] = {"arr": None, "ts": 0.0}
_last_shot_lock = threading.Lock()


@app.get("/api/screenshot")
def api_screenshot() -> Response:
    """Full-screen PNG for the XY picker / region selector."""
    import cv2

    try:
        arr = capture.capture_array()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Capture failed: {exc}")
    with _last_shot_lock:
        _last_shot["arr"] = arr
        _last_shot["ts"] = time.time()
    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise HTTPException(500, "PNG encode failed")
    return Response(content=buf.tobytes(), media_type="image/png")


@app.get("/api/screen-size")
def api_screen_size() -> dict[str, int]:
    w, h = capture.screen_size()
    return {"width": w, "height": h}


# --- Templates -------------------------------------------------------------

@app.get("/api/templates/{flow}")
def api_list_templates(flow: str) -> list[dict[str, Any]]:
    tdir = config.template_dir_for(flow)
    out = []
    for p in sorted(tdir.glob("*.png")):
        out.append({"name": p.name, "path": f"templates/{config._safe_name(flow)}/{p.name}", "modified": p.stat().st_mtime})
    return out


@app.get("/api/template-image")
def api_template_image(path: str) -> FileResponse:
    """Serve a template PNG by its project-relative path."""
    full = (config.ROOT / path).resolve()
    if not str(full).startswith(str(config.TEMPLATES_DIR.resolve())) or not full.exists():
        raise HTTPException(404, "Template not found")
    return FileResponse(full, media_type="image/png")


@app.post("/api/templates/{flow}/capture")
def api_capture_template(flow: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Crop a region from the screenshot shown in the overlay, save as PNG.

    payload: {left, top, width, height, name?}
    """
    import cv2

    try:
        left = int(payload["left"]); top = int(payload["top"])
        width = int(payload["width"]); height = int(payload["height"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "left/top/width/height required")
    if width <= 0 or height <= 0:
        raise HTTPException(400, "width and height must be positive")

    # Crop from the image the user actually saw and dragged on (see
    # _last_shot above). Only fall back to a fresh capture if none exists.
    with _last_shot_lock:
        arr = _last_shot["arr"]
    if arr is not None:
        h, w = arr.shape[:2]
        left = max(0, min(left, w - 1)); top = max(0, min(top, h - 1))
        width = min(width, w - left); height = min(height, h - top)
        crop = arr[top:top + height, left:left + width]
        ok, buf = cv2.imencode(".png", crop)
        if not ok:
            raise HTTPException(500, "PNG encode failed")
        png = buf.tobytes()
    else:
        png = capture.capture_png((left, top, width, height))
    tdir = config.template_dir_for(flow)
    name = config._safe_name(payload.get("name") or f"template_{int(time.time())}")
    fname = f"{name}.png"
    (tdir / fname).write_bytes(png)

    # Store DPI metadata alongside for the mismatch warning (PRD §5).
    scale = _current_dpi_scale()
    (tdir / f"{name}.meta.json").write_text(
        f'{{"dpi_scale": {scale}, "captured": {time.time()}}}', encoding="utf-8"
    )
    rel = f"templates/{config._safe_name(flow)}/{fname}"
    return {"ok": True, "name": fname, "path": rel, "dpi_scale": scale}


def _current_dpi_scale() -> float:
    # Awareness is set once at process startup (see server.py / runner.py).
    return capture.dpi_scale()


# --- Run control (REST + WebSocket) ---------------------------------------

@app.post("/api/run/{name}")
def api_run_flow(name: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    try:
        flow = storage.load_flow(name)
    except FileNotFoundError:
        raise HTTPException(404, f"Flow '{name}' not found")
    variables = {k: str(v) for k, v in (payload.get("variables") or {}).items()}
    started = manager.start(flow, variables)
    if not started:
        raise HTTPException(409, "A run is already in progress")
    return {"ok": True}


@app.post("/api/run/control/{action}")
def api_run_control(action: str) -> dict[str, Any]:
    if action == "stop":
        manager.stop()
    elif action == "pause":
        manager.pause()
    elif action == "resume":
        manager.resume()
    else:
        raise HTTPException(400, "Unknown action")
    return {"ok": True}


@app.get("/api/run/status")
def api_run_status() -> dict[str, Any]:
    res = manager.result
    return {
        "running": manager.is_running,
        "result": res.__dict__ if res else None,
    }


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket) -> None:
    """Streams run events to the UI. Client may also send control messages."""
    await ws.accept()
    q = manager.add_listener()
    loop = asyncio.get_event_loop()

    async def pump_incoming() -> None:
        try:
            while True:
                msg = await ws.receive_json()
                action = msg.get("action")
                if action == "stop":
                    manager.stop()
                elif action == "pause":
                    manager.pause()
                elif action == "resume":
                    manager.resume()
        except (WebSocketDisconnect, RuntimeError):
            pass

    incoming = asyncio.create_task(pump_incoming())
    try:
        while True:
            # Poll with a timeout so a disconnected/idle client releases the
            # worker thread instead of blocking on q.get forever.
            try:
                event = await loop.run_in_executor(None, q.get, True, 1.0)
            except queue.Empty:
                if incoming.done():  # client disconnected
                    break
                continue
            await ws.send_json(event)
            # `run_finished` is terminal; stop blocking on the queue afterwards.
            if event.get("type") == "run_finished":
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        incoming.cancel()
        manager.remove_listener(q)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# --- Static frontend (built React app) ------------------------------------
# Mounted last so it does not shadow the /api and /health routes above.

_DIST = config.ROOT / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="static")
