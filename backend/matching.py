"""Template image matching using OpenCV (TM_CCOEFF_NORMED), per PRD §5."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from . import capture


@dataclass
class MatchResult:
    found: bool
    confidence: float
    # Center of the matched template in absolute screen coordinates.
    x: int
    y: int
    # Top-left of the match (absolute screen coordinates).
    left: int
    top: int


def match_template(
    template_path: str | Path,
    confidence: float = 0.85,
    region: Optional[tuple[int, int, int, int]] = None,
    grayscale: bool = True,
) -> MatchResult:
    """Search the screen (or a region) for the template image.

    region = (left, top, width, height); when given, results are offset back
    into absolute screen coordinates.
    """
    import cv2

    tpl = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if tpl is None:
        raise FileNotFoundError(f"Template not found or unreadable: {template_path}")

    screen = capture.capture_array(region)

    if grayscale:
        screen_m = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        tpl_m = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    else:
        screen_m, tpl_m = screen, tpl

    th, tw = tpl_m.shape[:2]
    sh, sw = screen_m.shape[:2]
    if th > sh or tw > sw:
        # Template larger than search area -> impossible match.
        return MatchResult(False, 0.0, 0, 0, 0, 0)

    res = cv2.matchTemplate(screen_m, tpl_m, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    off_x = region[0] if region else 0
    off_y = region[1] if region else 0
    left = int(max_loc[0]) + off_x
    top = int(max_loc[1]) + off_y
    cx = left + tw // 2
    cy = top + th // 2

    return MatchResult(
        found=bool(max_val >= confidence),
        confidence=float(max_val),
        x=cx,
        y=cy,
        left=left,
        top=top,
    )
