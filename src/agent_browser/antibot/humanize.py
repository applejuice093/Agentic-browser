"""Human-like mouse/keyboard timing (M8)."""

from __future__ import annotations

import random


class HumanizedInput:
    """Delay and path helpers for more natural automation."""

    def __init__(self, *, min_delay_ms: float = 30, max_delay_ms: float = 120) -> None:
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms

    def keystroke_delay_ms(self) -> float:
        return random.uniform(self.min_delay_ms, self.max_delay_ms)

    def click_delay_ms(self) -> float:
        return random.uniform(self.min_delay_ms * 2, self.max_delay_ms * 3)
