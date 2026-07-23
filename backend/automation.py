"""Mouse / keyboard / clipboard automation wrappers (pyautogui + pyperclip)."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional


def _pg():
    """Lazily import and configure pyautogui."""
    import pyautogui

    pyautogui.PAUSE = 0  # we manage our own timing
    return pyautogui


def _mouse():
    """The hardware-like mouse backend on Windows, else None.

    Routing moves/holds through mouse_event (not pyautogui's SetCursorPos) is
    what makes a click-drag register in emulators and games — see
    backend/mouseinput.py.
    """
    import sys

    if sys.platform != "win32":
        return None
    try:
        from . import mouseinput

        return mouseinput
    except Exception:
        return None


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


# Buttons currently held down, so a move can tell a plain move from a drag.
_held_buttons: set[str] = set()


def reset_button_state() -> None:
    """Forget any held buttons (call at run start; a prior run may have aborted
    mid-drag without releasing)."""
    _held_buttons.clear()


def _place(px: int, py: int) -> None:
    """Position the cursor precisely at a pixel.

    Plain moves use SetCursorPos (via pyautogui): it takes coordinates directly
    in the screen's pixel space — the same space the XY picker uses — so the
    cursor lands exactly on the picked pixel under any DPI scale. While a button
    is held, route through the hardware-like backend so the move also registers
    as a real drag in emulators/games (which ignore SetCursorPos-only motion).
    """
    m = _mouse()
    if _held_buttons and m is not None:
        m.move_to(px, py)      # SetCursorPos + a raw MOVE event
    else:
        _pg().moveTo(px, py, duration=0)


def mouse_move(x: int, y: int, duration_ms: int = 0, easing: str = "linear",
               abort_check: Optional[Callable[[], bool]] = None) -> None:
    """Move the cursor to (x, y).

    A move with a duration is broken into small steps: this keeps the panic
    hotkey responsive (pyautogui's own `duration` blocks uninterruptibly, PRD
    §7.4) and, during a drag, gives the dragged control the stream of
    intermediate positions it needs to follow — a single jump to the endpoint
    is often seen as no drag at all.
    """
    duration = max(0, duration_ms) / 1000.0

    # Instant move, or no way to check for abort: a single placement is fine.
    if duration <= 0.03 or abort_check is None:
        _place(x, y)
        return

    tween = _tween(easing)
    start_x, start_y = _pg().position()
    steps = max(1, int(duration / 0.02))  # ~20 ms per step
    for i in range(1, steps + 1):
        if abort_check():
            return
        frac = tween(i / steps)
        _place(round(start_x + (x - start_x) * frac), round(start_y + (y - start_y) * frac))
        time.sleep(duration / steps)
    _place(x, y)


def mouse_down(button: str = "left", x: Optional[int] = None, y: Optional[int] = None) -> None:
    if x is not None and y is not None:
        _pg().moveTo(x, y, duration=0)  # precise grab point
    m = _mouse()
    _held_buttons.add(button)
    if m is not None:
        m.button_down(button)
    else:
        _pg().mouseDown(button=button)


def mouse_up(button: str = "left", x: Optional[int] = None, y: Optional[int] = None) -> None:
    if x is not None and y is not None:
        # A held button means this is the end of a drag: keep it hardware-like
        # so the release is seen at the final spot. Otherwise position precisely.
        _place(x, y)
    m = _mouse()
    if m is not None:
        m.button_up(button)
    else:
        _pg().mouseUp(button=button)
    _held_buttons.discard(button)


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


def _unicode_typing() -> Optional[Any]:
    """The sendinput module when Unicode typing is usable, else None."""
    import sys

    if sys.platform != "win32":
        return None
    try:
        from . import sendinput

        return sendinput
    except Exception:
        return None


def type_text(text: str, per_char_delay_ms: int = 0) -> None:
    """Type text, independent of the active keyboard layout.

    pyautogui.typewrite presses virtual keys as though the US layout were
    active. With a non-Latin layout selected (RU/UA/…) Windows maps those key
    positions through that layout, so letters arrive as the wrong characters —
    while digits and '.' occupy the same keys in both layouts and appear to
    work. Sending each character as a Unicode event avoids the layout entirely
    and also covers accents/emoji, which typewrite silently drops.

    Enter/Tab are still sent as real keys: a WM_CHAR newline is ignored by most
    inputs, whereas Enter is what "type a line" is expected to mean.
    """
    si = _unicode_typing()
    delay = max(0, per_char_delay_ms) / 1000.0

    if si is None:  # non-Windows: best effort via pyautogui
        _pg().typewrite(text, interval=delay)
        return

    for ch in text:
        if ch == "\n":
            key_press("enter", 30)
        elif ch == "\t":
            key_press("tab", 30)
        elif ch == "\r":
            continue  # CRLF: the \n already produced the Enter
        else:
            si.type_char(ch)
        if delay:
            time.sleep(delay)


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
