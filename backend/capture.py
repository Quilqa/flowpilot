"""Screen capture via mss, returning numpy BGR arrays / PNG bytes."""
from __future__ import annotations

import io
from typing import Optional

import numpy as np


def _grab(region: Optional[tuple[int, int, int, int]] = None) -> np.ndarray:
    """Capture the primary monitor (or a region) as a BGR numpy array.

    region = (left, top, width, height) in pixels.
    """
    import mss  # lazy import

    with mss.mss() as sct:
        if region is not None:
            left, top, width, height = region
            mon = {"left": left, "top": top, "width": width, "height": height}
        else:
            mon = sct.monitors[1]  # primary monitor (index 0 is the virtual union)
        raw = sct.grab(mon)
        # mss returns BGRA; drop alpha, keep BGR for OpenCV.
        arr = np.asarray(raw)[:, :, :3]
        return np.ascontiguousarray(arr)


def capture_array(region: Optional[tuple[int, int, int, int]] = None) -> np.ndarray:
    return _grab(region)


def capture_png(region: Optional[tuple[int, int, int, int]] = None) -> bytes:
    """Capture and encode to PNG bytes (BGR -> PNG)."""
    import cv2

    arr = _grab(region)
    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        raise RuntimeError("Failed to encode screenshot to PNG")
    return buf.tobytes()


def screen_size() -> tuple[int, int]:
    """Return (width, height) of the primary monitor."""
    import mss

    with mss.mss() as sct:
        mon = sct.monitors[1]
        return mon["width"], mon["height"]


def set_dpi_awareness() -> None:
    """Make the process per-monitor DPI aware.

    Must run once at startup, before any screen capture or mouse movement —
    changing awareness mid-process shifts the coordinate space, so a pixel
    picked from a screenshot would no longer match where clicks land.

    Prefer Per-Monitor-Aware **v2** (Win10 1703+): under v1 the legacy metrics
    (GetSystemMetrics, cursor positioning) can report scaled rather than
    physical pixels when the monitor layout changes, which makes a picked pixel
    miss its target on a scaled display. v2 keeps them physical and consistent.
    Fall back to v1, then the system-DPI API, on older Windows.
    """
    import ctypes

    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4, passed as a pseudo-handle.
    try:
        ctx = ctypes.c_void_p(-4)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctx):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE (v1)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # system-DPI aware
    except Exception:
        pass


def dpi_report() -> dict:
    """Diagnostic: compare the screenshot's pixel space (mss) with the metrics
    used for cursor positioning. A mismatch is why a picked pixel can miss —
    they must agree for the XY picker to be accurate."""
    import ctypes

    out: dict = {}
    try:
        u = ctypes.windll.user32
        out["get_system_metrics"] = [u.GetSystemMetrics(0), u.GetSystemMetrics(1)]
    except Exception as exc:  # noqa: BLE001
        out["get_system_metrics"] = f"error: {exc}"
    try:
        out["mss_primary"] = list(screen_size())
    except Exception as exc:  # noqa: BLE001
        out["mss_primary"] = f"error: {exc}"
    gsm, mss = out.get("get_system_metrics"), out.get("mss_primary")
    out["consistent"] = isinstance(gsm, list) and gsm == mss
    out["dpi_scale"] = dpi_scale()
    return out


def dpi_scale() -> float:
    """Current display scale factor (1.0 == 100%)."""
    try:
        import ctypes

        return round(ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100.0, 2)
    except Exception:
        return 1.0


def png_to_array(data: bytes) -> np.ndarray:
    import cv2

    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Invalid PNG data")
    return img
