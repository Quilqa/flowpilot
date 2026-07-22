"""Low-level keyboard input via the Win32 SendInput API with scan codes.

Why this exists (PRD §2 / §10 "SendInput fallback"): pyautogui sends keys
through the legacy keybd_event API using virtual-key codes and a zero scan
code. Applications that read *raw input* or scan codes — games, Android
emulators (MuMu, LDPlayer, BlueStacks) and their key-mapping overlays — ignore
such events entirely. SendInput with KEYEVENTF_SCANCODE produces events that
are indistinguishable from real hardware key presses for these apps, while
remaining fully compatible with normal applications.

Windows-only; import lazily and fall back to pyautogui elsewhere.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

# --- Win32 structures --------------------------------------------------------

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001
MAPVK_VK_TO_VSC = 0

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("padding", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUT_UNION)]


# --- Key name → virtual-key code ----------------------------------------------

VK = {
    # modifiers
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
    # navigation / editing
    "enter": 0x0D, "esc": 0x1B, "tab": 0x09, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "capslock": 0x14, "printscreen": 0x2C, "pause": 0x13,
    # numpad
    "num0": 0x60, "num1": 0x61, "num2": 0x62, "num3": 0x63, "num4": 0x64,
    "num5": 0x65, "num6": 0x66, "num7": 0x67, "num8": 0x68, "num9": 0x69,
    "multiply": 0x6A, "add": 0x6B, "subtract": 0x6D, "decimal": 0x6E, "divide": 0x6F,
    # punctuation (US layout)
    "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF, "`": 0xC0,
}
# letters and digits
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK[_c] = ord(_c.upper())
for _d in "0123456789":
    VK[_d] = ord(_d)
# F1–F24
for _i in range(1, 25):
    VK[f"f{_i}"] = 0x70 + (_i - 1)

# Keys whose scan codes need the EXTENDEDKEY flag (they share scan codes with
# numpad keys and are disambiguated by the E0 prefix on real hardware).
EXTENDED = {
    "insert", "delete", "home", "end", "pageup", "pagedown",
    "up", "down", "left", "right", "divide", "printscreen", "win",
}


def supported(key: str) -> bool:
    return key in VK


def _send(vk: int, scan: int, flags: int) -> None:
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.union.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    sent = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        raise OSError(f"SendInput failed (sent={sent}, err={ctypes.GetLastError()})")


def key_event(key: str, up: bool) -> None:
    """Send a single key down/up event with a real scan code."""
    vk = VK[key]
    scan = ctypes.windll.user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_SCANCODE
    if key in EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    if up:
        flags |= KEYEVENTF_KEYUP
    # Keep wVk populated too: some apps read the virtual key, some the scan
    # code; providing both maximizes compatibility.
    _send(vk, scan, flags)


def key_down(key: str) -> None:
    key_event(key, up=False)


def key_up(key: str) -> None:
    key_event(key, up=True)


# --- Text entry --------------------------------------------------------------


def _utf16_units(ch: str) -> list[int]:
    """The UTF-16 code units of a character (a surrogate pair above U+FFFF)."""
    data = ch.encode("utf-16-le")
    return [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]


def type_char(ch: str) -> None:
    """Type one character as a Unicode event, independent of keyboard layout.

    The scan-code path above sends a key *position*, which Windows translates
    through the active layout — so pressing the "A" key with a Russian layout
    selected yields 'ф'. Digits and '.' sit on the same keys in every Latin
    /Cyrillic layout, which is why they alone appeared to work.

    KEYEVENTF_UNICODE instead delivers the character itself (the target gets
    WM_CHAR), so text arrives correctly whatever layout is active, and
    accented/emoji characters work without a clipboard round-trip. wVk must be
    0 for these events; the code unit travels in wScan.
    """
    for unit in _utf16_units(ch):
        _send(0, unit, KEYEVENTF_UNICODE)
        _send(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
