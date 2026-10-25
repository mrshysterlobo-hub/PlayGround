from __future__ import annotations

import logging
import time
from typing import ClassVar

from .flow import FlowTask
from .options import (
    as_non_negative_float,
    as_positive_float,
    resolve_templates,
)

logger = logging.getLogger("lordsbot")


class GuildHelpTask(FlowTask):
    name = "guild_help"
    OPTIONAL: ClassVar[frozenset[str]] = frozenset({"marker", "all", "close"})

    TEMPLATES: ClassVar[dict[str, str]] = {
        "guild": "guild_button",
        "marker": "guild_marker",
        "all": "help_all",
        "hand": "help_hand",
        "close": "close_button",
    }

    def __init__(
        self,
        cooldown: float = 600.0,
        timeout: float = 20.0,
        empty_grace: float = 2.0,
        tap_delay: float = 0.8,
        templates=None,
        threshold: float | None = None,
        error_cooldown: float = 60.0,
    ) -> None:
        self.cooldown = as_non_negative_float(cooldown, "cooldown")
        self.timeout = as_positive_float(timeout, "timeout")
        self.empty_grace = as_non_negative_float(empty_grace, "empty_grace")
        self.tap_delay = as_positive_float(tap_delay, "tap_delay")
        super().__init__(resolve_templates(self.TEMPLATES, templates), threshold, error_cooldown)
        self._helps = 0
        self._empty_since: float | None = None
        self._clearing_checks = 0

    def phase_start(self, bot) -> None:
        self._helps = 0
        self._empty_since = None
        self.enter("open_guild")

    def phase_open_guild(self, bot) -> float | None:
        if self.find_optional(bot, self.t("marker")) or self.find_optional(bot, self.t("hand")):
            self.enter("help")
            return None
        if self.tap_optional(bot, self.t("guild")):
            self.enter("help")
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_help(self, bot) -> float | None:
        if self.tap_optional(bot, self.t("all")):
            self._helps += 1
            self._empty_since = None
            self._clearing_checks = 0
            self.enter("clearing")
            return self.tap_delay
        if self.tap(bot, self.t("hand")):
            self._helps += 1
            self._empty_since = None
            logger.info("guild_help: helped guild member (%d)", self._helps)
            return self.tap_delay
        now = time.monotonic()
        if self._empty_since is None:
            self._empty_since = now
            return 1.0
        if now - self._empty_since >= self.empty_grace:
            self.enter("finish")
            return None
        return bot.poll_interval

    def phase_clearing(self, bot) -> float | None:
        if self.tap_optional(bot, self.t("all")):
            self._clearing_checks = 0
            return self.tap_delay
        self._clearing_checks += 1
        if self._clearing_checks >= 3 or self.elapsed() > 1.5:
            self.enter("help")
            return None
        return bot.poll_interval

    def phase_finish(self, bot) -> float | None:
        self.tap_optional(bot, self.t("close"))
        bot.back()
        logger.info("guild_help: assisted %d time(s)", self._helps)
        return self.complete(self.cooldown)
