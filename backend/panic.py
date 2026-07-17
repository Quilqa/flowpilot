"""Global panic hotkey registration (PRD §7.4). Aborts any active run."""
from __future__ import annotations

from typing import Callable


def register(hotkey: str, on_panic: Callable[[], None]) -> bool:
    """Register a global hotkey. Returns True on success.

    Uses the `keyboard` library, which needs no admin rights for hotkeys but
    may on some systems. Failure is non-fatal.
    """
    try:
        import keyboard

        keyboard.add_hotkey(hotkey, on_panic, suppress=False)
        return True
    except Exception:
        return False
