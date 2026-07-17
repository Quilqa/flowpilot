"""Mouse / keyboard / clipboard automation wrappers (pyautogui + pyperclip)."""
from __future__ import annotations

import time
from typing import Callable, Optional


def _pg():
    """Lazily import and configure pyautogui."""
    import pyautogui

    pyautogui.PAUSE = 0  # we manage our own timing
    return pyautogui


def set_failsafe(enabled: bool) -> None:
    try:
        import pyautogui

        pyautogui.FAILSAFE = enabled
    except Exception:
        pass


# --- Mouse -----------------------------------------------------------------

_EASING = {
    "linear": None,  # pyautogui.linear, set lazily
    "ease-in-out": None,
}


def _tween(easing: str):
    import pyautogui

    if easing == "ease-in-out":
        return pyautogui.easeInOutQuad
    return pyautogui.linear


def mouse_move(x: int, y: int, duration_ms: int = 0, easing: str = "linear",
               abort_check: Optional[Callable[[], bool]] = None) -> None:
    """Move the cursor to (x, y).

    When a duration is set, the move is broken into small steps so that a
    long/eased move remains interruptible via `abort_check` (returns True to
    stop early) — pyautogui's own `duration` blocks uninterruptibly, which
    would delay the panic hotkey (PRD §7.4).
    """
    pg = _pg()
    duration = max(0, duration_ms) / 1000.0
    # Short or instant moves: a single moveTo is fine and cheaper.
    if duration <= 0.03 or abort_check is None:
        pg.moveTo(x, y, duration=duration, tween=_tween(easing))
        return

    tween = _tween(easing)
    start_x, start_y = pg.position()
    steps = max(1, int(duration / 0.02))  # ~20 ms per step
    for i in range(1, steps + 1):
        if abort_check():
            return
        frac = tween(i / steps)
        nx = start_x + (x - start_x) * frac
        ny = start_y + (y - start_y) * frac
        pg.moveTo(round(nx), round(ny), duration=0)
        time.sleep(duration / steps)
    pg.moveTo(x, y, duration=0)


def mouse_down(button: str = "left", x: Optional[int] = None, y: Optional[int] = None) -> None:
    pg = _pg()
    if x is not None and y is not None:
        pg.moveTo(x, y)
    pg.mouseDown(button=button)


def mouse_up(button: str = "left", x: Optional[int] = None, y: Optional[int] = None) -> None:
    pg = _pg()
    if x is not None and y is not None:
        pg.moveTo(x, y)
    pg.mouseUp(button=button)


def mouse_click(
    button: str = "left",
    x: Optional[int] = None,
    y: Optional[int] = None,
    clicks: int = 1,
    interval_ms: int = 0,
) -> None:
    pg = _pg()
    kwargs = {"button": button, "clicks": max(1, clicks), "interval": max(0, interval_ms) / 1000.0}
    if x is not None and y is not None:
        pg.click(x=x, y=y, **kwargs)
    else:
        pg.click(**kwargs)


def mouse_scroll(direction: str = "down", amount: int = 3) -> None:
    pg = _pg()
    clicks = abs(int(amount)) * 100
    if direction == "down":
        clicks = -clicks
    pg.scroll(clicks)


# --- Keyboard --------------------------------------------------------------

# Map friendly names to pyautogui key names.
KEY_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "win": "win",
    "windows": "win",
    "cmd": "win",
    "return": "enter",
    "esc": "esc",
    "escape": "esc",
}


def _norm_key(key: str) -> str:
    k = key.strip().lower()
    return KEY_ALIASES.get(k, k)


def _scan_key(key: str, up: bool) -> bool:
    """Try the SendInput scan-code backend. Returns True if it handled the key.

    Emulators/games (MuMu, BlueStacks, …) hook raw input and ignore
    pyautogui's legacy keybd_event events; scan-code SendInput looks like real
    hardware to them and works everywhere else too (PRD §2 SendInput fallback).
    """
    import sys

    if sys.platform != "win32":
        return False
    try:
        from . import sendinput

        if not sendinput.supported(key):
            return False
        sendinput.key_event(key, up=up)
        return True
    except Exception:
        return False


def key_down(key: str) -> None:
    k = _norm_key(key)
    if not _scan_key(k, up=False):
        _pg().keyDown(k)


def key_up(key: str) -> None:
    k = _norm_key(key)
    if not _scan_key(k, up=True):
        _pg().keyUp(k)


def key_press(key: str, hold_ms: int = 30) -> None:
    """Press a single key or a '+'-joined combo (e.g. 'ctrl+shift+s').

    A short down→up hold is kept between events: emulator key-mappers poll
    input state and can miss a zero-duration press.
    """
    parts = [_norm_key(p) for p in key.replace(" ", "").split("+") if p]
    if not parts:
        return
    for p in parts:
        key_down(p)
    time.sleep(max(0, hold_ms) / 1000.0)
    for p in reversed(parts):
        key_up(p)


def type_text(text: str, per_char_delay_ms: int = 0) -> None:
    """Type text, handling non-ASCII characters.

    pyautogui.typewrite silently skips characters outside its key table
    (accents, emoji, etc.). Type the ASCII-printable run directly for speed,
    and paste anything else via the clipboard so nothing is dropped.
    """
    pg = _pg()
    interval = max(0, per_char_delay_ms) / 1000.0

    def typeable(ch: str) -> bool:
        return 32 <= ord(ch) < 127 or ch in ("\n", "\t")

    # Fast path: all-ASCII text types directly.
    if all(typeable(c) for c in text):
        pg.typewrite(text, interval=interval)
        return

    for ch in text:
        if typeable(ch):
            pg.typewrite(ch, interval=interval)
        else:
            paste_value(ch)  # clipboard round-trip for unsupported characters
            if interval:
                time.sleep(interval)


# Preset shortcuts (name -> combo string).
SHORTCUTS = {
    "copy": "ctrl+c",
    "paste": "ctrl+v",
    "cut": "ctrl+x",
    "select_all": "ctrl+a",
    "save": "ctrl+s",
    "alt_tab": "alt+tab",
    "alt_shift_tab": "alt+shift+tab",
    "win_d": "win+d",
    "enter": "enter",
    "esc": "esc",
    "tab": "tab",
}


def shortcut(preset: str, custom_combo: str = "") -> None:
    combo = SHORTCUTS.get(preset)
    if combo is None:
        combo = custom_combo or preset
    key_press(combo)


# --- Clipboard -------------------------------------------------------------

def clipboard_get() -> str:
    import pyperclip

    return pyperclip.paste()


def clipboard_set(value: str) -> None:
    import pyperclip

    pyperclip.copy(value)


def copy_selection_to_clipboard(settle_ms: int = 150) -> str:
    """Ctrl+C then read the clipboard."""
    key_press("ctrl+c")
    time.sleep(settle_ms / 1000.0)
    return clipboard_get()


def paste_value(value: str, settle_ms: int = 80) -> None:
    """Put value on the clipboard and Ctrl+V it."""
    clipboard_set(value)
    time.sleep(settle_ms / 1000.0)
    key_press("ctrl+v")
