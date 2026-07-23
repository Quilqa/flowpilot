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
from ctypes import wintypes

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

MOUSEEVENTF_VIRTUALDESK = 0x4000

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


def _virtual_rect() -> tuple[int, int, int, int]:
    """(left, top, width, height) of the whole virtual desktop, in the pixel
    space our positioning uses. Absolute mouse_event coordinates are normalized
    against this with the VIRTUALDESK flag so multi-monitor layouts map right."""
    u = ctypes.windll.user32
    return (u.GetSystemMetrics(SM_XVIRTUALSCREEN), u.GetSystemMetrics(SM_YVIRTUALSCREEN),
            u.GetSystemMetrics(SM_CXVIRTUALSCREEN), u.GetSystemMetrics(SM_CYVIRTUALSCREEN))


def _raw_move_at_cursor() -> None:
    """Emit a hardware-like absolute MOVE at the cursor's *current* position.

    Derived from the real cursor position (GetCursorPos), so it lands exactly
    where SetCursorPos already put it — no dependence on a separate coordinate
    round-trip — while still generating the raw-input MOVE that emulators need
    to see a drag.
    """
    u = ctypes.windll.user32
    pt = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    vx, vy, vw, vh = _virtual_rect()
    ax = int(round((pt.x - vx) * 65535 / max(1, vw - 1)))
    ay = int(round((pt.y - vy) * 65535 / max(1, vh - 1)))
    ax = max(0, min(65535, ax))
    ay = max(0, min(65535, ay))
    u.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, ax, ay, 0, 0)


def move_to(x: int, y: int) -> None:
    """Position the cursor exactly, then fire a raw move so drags register.

    SetCursorPos takes coordinates directly in the screen's pixel space — the
    same space the XY picker's screenshot uses — so the cursor lands precisely
    on the picked pixel regardless of DPI scaling. The extra raw MOVE event (at
    that exact position) is what makes a held-button drag show up in emulators
    and games, which ignore SetCursorPos-only movement.
    """
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    _raw_move_at_cursor()


def button_down(button: str = "left") -> None:
    """Press a mouse button at the current cursor position."""
    down, _ = _BUTTONS.get(button, _BUTTONS["left"])
    ctypes.windll.user32.mouse_event(down, 0, 0, 0, 0)


def button_up(button: str = "left") -> None:
    """Release a mouse button at the current cursor position."""
    _, up = _BUTTONS.get(button, _BUTTONS["left"])
    ctypes.windll.user32.mouse_event(up, 0, 0, 0, 0)
