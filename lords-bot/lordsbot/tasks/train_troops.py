from __future__ import annotations

import logging
from typing import ClassVar

from .flow import FlowTask
from .options import (
    as_non_negative_float,
    as_positive_float,
    as_positive_int,
    resolve_templates,
)

logger = logging.getLogger("lordsbot")


class TrainTroopsTask(FlowTask):
    name = "train_troops"
    OPTIONAL: ClassVar[frozenset[str]] = frozenset(
        {"tab", "max", "plus", "confirm", "queue_full", "marker", "close"}
    )

    TEMPLATES: ClassVar[dict[str, str]] = {
        "training": "training_entry",
        "city": "city_button",
        "tab": "train_tab",
        "troop": "troop_infantry",
        "tier": "tier_1",
        "max": "quantity_max",
        "plus": "quantity_plus",
        "start": "train_start",
        "confirm": "train_confirm",
        "queue_full": "queue_full",
        "marker": "training_marker",
        "close": "close_button",
    }

    def __init__(
        self,
        plus_taps: int = 0,
        cooldown: float = 300.0,
        timeout: float = 20.0,
        templates=None,
        threshold: float | None = None,
        error_cooldown: float = 60.0,
    ) -> None:
        self.plus_taps = as_positive_int(plus_taps, "plus_taps", minimum=0)
        self.cooldown = as_non_negative_float(cooldown, "cooldown")
        self.timeout = as_positive_float(timeout, "timeout")
        super().__init__(resolve_templates(self.TEMPLATES, templates), threshold, error_cooldown)
        self._remaining_plus = 0
        self._tab_done = False
        self._tier_done = False

    def phase_start(self, bot) -> None:
        self._remaining_plus = self.plus_taps
        self._tab_done = False
        self._tier_done = False
        self.enter("to_city")

    def phase_to_city(self, bot) -> float | None:
        if self.find(bot, self.t("training")):
            self.enter("open_training")
            return None
        if self.tap(bot, self.t("city")):
            return 1.5
        if self.find_optional(bot, self.t("queue_full")):
            logger.info("train_troops: training queue is full")
            return self.complete(self.cooldown)
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_open_training(self, bot) -> float | None:
        if self.tap(bot, self.t("training")):
            self.enter("configure")
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_configure(self, bot) -> float | None:
        if not self._tab_done and self.tap_optional(bot, self.t("tab")):
            self._tab_done = True
            return 1.0
        if self.tap(bot, self.t("troop")):
            self.enter("tier")
            return 1.0
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_tier(self, bot) -> float | None:
        if not self._tier_done and self.tap_optional(bot, self.t("tier")):
            self._tier_done = True
            return 1.0
        self.enter("quantity")
        return None

    def phase_quantity(self, bot) -> float | None:
        if self.tap_optional(bot, self.t("max")):
            self.enter("start_training")
            return 1.0
        if self._remaining_plus > 0:
            if self.tap_optional(bot, self.t("plus")):
                self._remaining_plus -= 1
                return 0.5
            self._remaining_plus = 0
        self.enter("start_training")
        return None

    def phase_start_training(self, bot) -> float | None:
        if self.find_optional(bot, self.t("queue_full")):
            logger.info("train_troops: training queue is full")
            return self.complete(self.cooldown)
        if self.tap(bot, self.t("start")):
            self.enter("confirm")
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_confirm(self, bot) -> float | None:
        if self.tap_optional(bot, self.t("confirm")):
            self.enter("done")
            return 1.5
        if self.timed_out(bot, 2.0, fallback="done"):
            return None
        return bot.poll_interval

    def phase_done(self, bot) -> float | None:
        return self.complete(self.cooldown)
