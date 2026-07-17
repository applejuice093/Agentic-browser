"""Human-like mouse/keyboard timing and paths (M8)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class Point:
    x: float
    y: float


class HumanizedInput:
    """
    Delay and path helpers for more natural automation.

    Ethical use: only for legitimate agent sessions you control.
    Does not bypass CAPTCHAs or break site terms — slows input to look less robotic.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        min_delay_ms: float = 30,
        max_delay_ms: float = 120,
        click_pause_ms: tuple[float, float] = (40, 180),
        move_steps: tuple[int, int] = (8, 20),
    ) -> None:
        self.enabled = enabled
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.click_pause_ms = click_pause_ms
        self.move_steps = move_steps
        self._last_pos: Point | None = None

    def keystroke_delay_ms(self) -> float:
        if not self.enabled:
            return 0.0
        return random.uniform(self.min_delay_ms, self.max_delay_ms)

    def click_delay_ms(self) -> float:
        if not self.enabled:
            return 0.0
        return random.uniform(self.click_pause_ms[0], self.click_pause_ms[1])

    def action_gap_ms(self) -> float:
        """Pause between high-level actions."""
        if not self.enabled:
            return 0.0
        return random.uniform(self.max_delay_ms, self.max_delay_ms * 3)

    def mouse_path(
        self,
        start: Point | tuple[float, float],
        end: Point | tuple[float, float],
        *,
        steps: int | None = None,
    ) -> list[Point]:
        """
        Generate a slightly curved path from start → end (ease-in-out + jitter).
        """
        if isinstance(start, tuple):
            start = Point(*start)
        if isinstance(end, tuple):
            end = Point(*end)
        if not self.enabled:
            return [end]
        n = steps or random.randint(self.move_steps[0], self.move_steps[1])
        n = max(2, n)
        # Control point for quadratic Bezier offset
        mid_x = (start.x + end.x) / 2 + random.uniform(-40, 40)
        mid_y = (start.y + end.y) / 2 + random.uniform(-40, 40)
        ctrl = Point(mid_x, mid_y)
        path: list[Point] = []
        for i in range(1, n + 1):
            t = i / n
            # ease-in-out
            te = t * t * (3 - 2 * t)
            # quadratic bezier
            x = (1 - te) ** 2 * start.x + 2 * (1 - te) * te * ctrl.x + te**2 * end.x
            y = (1 - te) ** 2 * start.y + 2 * (1 - te) * te * ctrl.y + te**2 * end.y
            if i < n:
                x += random.uniform(-1.5, 1.5)
                y += random.uniform(-1.5, 1.5)
            path.append(Point(x, y))
        self._last_pos = path[-1]
        return path

    def target_point_from_box(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> Point:
        """Pick a click point inside a box (not always center)."""
        if not self.enabled:
            return Point(x + width / 2, y + height / 2)
        # Bias toward center with Gaussian-ish noise
        px = x + width * random.gauss(0.5, 0.12)
        py = y + height * random.gauss(0.5, 0.12)
        px = min(max(px, x + 1), x + max(width - 1, 1))
        py = min(max(py, y + 1), y + max(height - 1, 1))
        return Point(px, py)

    def typing_profile(self, text: str) -> list[float]:
        """Per-character delays; occasional longer pauses on spaces/punctuation."""
        delays: list[float] = []
        for ch in text:
            d = self.keystroke_delay_ms()
            if ch in " .,!?;:":
                d *= random.uniform(1.2, 2.0)
            delays.append(d)
        return delays
