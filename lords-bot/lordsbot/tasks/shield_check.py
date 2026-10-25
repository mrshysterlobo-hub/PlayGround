from __future__ import annotations

import logging
from typing import ClassVar

from .flow import FlowTask
from .options import (
    as_non_negative_float,
    as_positive_float,
    resolve_templates,
)

logger = logging.getLogger("lordsbot")


class ShieldCheckTask(FlowTask):
    name = "shield_check"
    OPTIONAL: ClassVar[frozenset[str]] = frozenset({"confirm", "close"})

    TEMPLATES: ClassVar[dict[str, str]] = {
        "active": "shield_active",
        "items": "items_button",
        "item": "shield_item",
        "use": "use_button",
        "confirm": "use_confirm",
        "city": "city_button",
        "close": "close_button",
    }

    def __init__(
        self,
        interval: float = 1800.0,
        retry: float = 300.0,
        timeout: float = 20.0,
        templates=None,
        threshold: float | None = None,
        error_cooldown: float = 120.0,
    ) -> None:
        self.interval = as_non_negative_float(interval, "interval")
        self.retry = as_non_negative_float(retry, "retry")
        self.timeout = as_positive_float(timeout, "timeout")
        super().__init__(resolve_templates(self.TEMPLATES, templates), threshold, error_cooldown)

    def phase_start(self, bot) -> None:
        self.enter("to_city")

    def phase_to_city(self, bot) -> float | None:
        if self.find(bot, self.t("active")):
            logger.info("shield_check: shield is active")
            return self.complete(self.interval)
        if self.tap(bot, self.t("items")):
            self.enter("inventory")
            return 1.5
        if self.tap(bot, self.t("city")):
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_inventory(self, bot) -> float | None:
        if self.tap(bot, self.t("item")):
            self.enter("use")
            return 1.0
        if self.timed_out(bot, 5.0, fallback="recover"):
            return None
        return bot.poll_interval

    def phase_use(self, bot) -> float | None:
        if self.tap(bot, self.t("use")):
            self.enter("confirm")
            return 1.0
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_confirm(self, bot) -> float | None:
        if self.tap_optional(bot, self.t("confirm")):
            self.enter("verify")
            return 1.5
        if self.timed_out(bot, 3.0, fallback="verify"):
            return None
        return bot.poll_interval

    def phase_verify(self, bot) -> float | None:
        if self.find(bot, self.t("active")):
            logger.info("shield_check: shield activated")
            return self.complete(self.interval)
        if self.timed_out(bot, 8.0, fallback="done"):
            logger.warning("shield_check: shield did not activate; is the item available?")
            return None
        return bot.poll_interval

    def phase_done(self, bot) -> float | None:
        return self.complete(self.retry)
