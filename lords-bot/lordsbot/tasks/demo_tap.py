from __future__ import annotations

import logging
import time

from .base import Task

logger = logging.getLogger("lordsbot")


class DemoTapTask(Task):
    name = "demo_tap"

    def __init__(self, template: str, cooldown: float = 5.0, threshold: float | None = None) -> None:
        if not isinstance(template, str) or not template.strip():
            raise ValueError("template must be a non-empty string")
        if cooldown < 0:
            raise ValueError("cooldown must be zero or greater")
        if threshold is not None and not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        self.template = template.strip()
        self.cooldown = float(cooldown)
        self.threshold = threshold
        self._last_tap = float("-inf")

    def step(self, bot) -> float | None:
        match = bot.find(self.template, self.threshold)
        if match is None:
            return bot.poll_interval
        now = time.monotonic()
        remaining = self.cooldown - (now - self._last_tap)
        if remaining > 0:
            return max(remaining, bot.poll_interval)
        bot.tap_match(match, label=f"task:{self.template}")
        self._last_tap = now
        logger.info("matched %s with score %.3f", self.template, match.score)
        return max(self.cooldown, bot.poll_interval)
