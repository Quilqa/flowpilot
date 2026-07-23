"""Low-level mouse input via Win32 `mouse_event` with absolute coordinates.

Why this exists (found the hard way, see PRD §2 "SendInput fallback" — the same
reasoning as the keyboard scan-code path): applications that read *raw* input —
games and Android emulators (MuMu, LDPlayer, BlueStacks) — ignore the
`SetCursorPos`-based moves pyautogui performs. A click-drag (holding the button
while moving) is never seen as a drag: the slider does not move at all, or only
jumps partway. `mouse_event` with `MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE`
produces events indistinguishable from real hardware, which those apps accept
as a genuine touch-drag. Normal desktop apps accept it too.

Absolute coordinates are 0..65535 fractions of the primary monitor, so this
relies on per-monitor DPI awareness already being set (capture.set_dpi_awareness)
and on the single-monitor assumption in the PRD.

Windows-only; import lazily and fall back to pyautogui elsewhere.
"""
from __future__ import annotations

import ctypes

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

_BUTTONS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

SM_CXSCREEN = 0
SM_CYSCREEN = 1


def _screen_size() -> tuple[int, int]:
    u = ctypes.windll.user32
    return u.GetSystemMetrics(SM_CXSCREEN), u.GetSystemMetrics(SM_CYSCREEN)


def _to_absolute(x: int, y: int) -> tuple[int, int]:
    """Pixel coordinates → the 0..65535 normalized space mouse_event expects."""
    cx, cy = _screen_size()
    ax = int(round(x * 65535 / max(1, cx - 1)))
    ay = int(round(y * 65535 / max(1, cy - 1)))
    return max(0, min(65535, ax)), max(0, min(65535, ay))


def move_to(x: int, y: int) -> None:
    """Move the cursor to a pixel position with a hardware-like absolute event."""
    ax, ay = _to_absolute(x, y)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, ax, ay, 0, 0)


def button_down(button: str = "left") -> None:
    """Press a mouse button at the current cursor position."""
    down, _ = _BUTTONS.get(button, _BUTTONS["left"])
    ctypes.windll.user32.mouse_event(down, 0, 0, 0, 0)


def button_up(button: str = "left") -> None:
    """Release a mouse button at the current cursor position."""
    _, up = _BUTTONS.get(button, _BUTTONS["left"])
    ctypes.windll.user32.mouse_event(up, 0, 0, 0, 0)
