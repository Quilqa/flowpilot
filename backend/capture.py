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
    """
    try:
        import ctypes

        # PROCESS_PER_MONITOR_DPI_AWARE = 2 (Windows 8.1+).
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


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
