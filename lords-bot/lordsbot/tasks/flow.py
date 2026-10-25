from __future__ import annotations

import logging
import time
from collections.abc import Mapping

from ..vision import Match, TemplateError
from .base import Task

logger = logging.getLogger("lordsbot")


class FlowTask(Task):
    name = "flow"
    TEMPLATES: Mapping[str, str] = {}
    OPTIONAL: frozenset[str] = frozenset()

    def __init__(
        self,
        templates: Mapping[str, str],
        threshold: float | None = None,
        error_cooldown: float = 60.0,
    ) -> None:
        if threshold is not None and not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        self.templates = dict(templates)
        self.threshold = threshold
        self.error_cooldown = float(error_cooldown)
        self._phase = "start"
        self._phase_since = time.monotonic()
        self._done_until = 0.0
        self._recovery_steps = 0
        self._missing: set[str] = set()

    def step(self, bot) -> float | None:
        remaining = self.remaining_cooldown()
        if remaining > 0:
            return remaining
        handler = getattr(self, f"phase_{self._phase}", None)
        if handler is None:
            raise RuntimeError(f"{self.name}: unknown phase {self._phase!r}")
        return handler(bot)

    def is_complete(self) -> bool:
        return self.remaining_cooldown() > 0

    def remaining_cooldown(self) -> float:
        return max(0.0, self._done_until - time.monotonic())

    def enter(self, phase: str) -> None:
        if phase != self._phase:
            logger.debug("%s: %s -> %s", self.name, self._phase, phase)
        self._phase = phase
        self._phase_since = time.monotonic()
        self._recovery_steps = 0

    def elapsed(self) -> float:
        return time.monotonic() - self._phase_since

    def complete(self, cooldown: float) -> float:
        self._phase = "start"
        self._phase_since = time.monotonic()
        self._done_until = time.monotonic() + max(0.0, cooldown)
        logger.info("%s: finished, cooldown %.0fs", self.name, cooldown)
        return self.remaining_cooldown()

    def timed_out(self, bot, seconds: float, fallback: str = "recover") -> bool:
        if self.elapsed() <= seconds:
            return False
        logger.warning(
            "%s: no progress in phase %s for %.0fs",
            self.name,
            self._phase,
            seconds,
        )
        try:
            path = bot.save_screenshot(f"{self.name}-{self._phase}")
            logger.warning("%s: saved debug frame %s", self.name, path)
        except OSError as exc:
            logger.warning("%s: could not save debug frame: %s", self.name, exc)
        self.enter(fallback)
        return True

    def t(self, key: str) -> str:
        try:
            return self.templates[key]
        except KeyError as exc:
            raise ValueError(f"{self.name}: unknown template key {key!r}") from exc

    def find(self, bot, template: str) -> Match | None:
        return bot.find(template, self.threshold)

    def tap(self, bot, template: str) -> bool:
        match = self.find(bot, template)
        if match is None:
            return False
        bot.tap_match(match, label=f"{self.name}:{template}")
        return True

    def find_optional(self, bot, template: str) -> Match | None:
        try:
            return self.find(bot, template)
        except TemplateError as exc:
            if template not in self._missing:
                self._missing.add(template)
                logger.info("%s: optional template %s unavailable: %s", self.name, template, exc)
            return None

    def tap_optional(self, bot, template: str) -> bool:
        match = self.find_optional(bot, template)
        if match is None:
            return False
        bot.tap_match(match, label=f"{self.name}:{template}")
        return True

    def phase_recover(self, bot) -> float | None:
        if self._recovery_steps >= 3:
            return self.complete(self.error_cooldown)
        self._recovery_steps += 1
        if self.tap_optional(bot, self.t("close")):
            return 1.0
        bot.back()
        return 1.0
