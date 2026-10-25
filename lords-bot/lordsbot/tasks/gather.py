from __future__ import annotations

import logging
from typing import ClassVar

from .flow import FlowTask
from .options import (
    as_non_negative_float,
    as_positive_float,
    as_positive_int,
    as_string_list,
    resolve_templates,
)

logger = logging.getLogger("lordsbot")

RESOURCES = ("food", "wood", "stone", "ore", "gold")


class GatherTask(FlowTask):
    name = "gather"
    OPTIONAL: ClassVar[frozenset[str]] = frozenset({"march_full", "no_results", "close"})

    TEMPLATES: ClassVar[dict[str, str]] = {
        "world": "world_button",
        "search": "search_button",
        "search_confirm": "search_confirm",
        "food": "resource_food",
        "wood": "resource_wood",
        "stone": "resource_stone",
        "ore": "resource_ore",
        "gold": "resource_gold",
        "tile": "resource_tile",
        "gather": "gather_button",
        "march": "march_button",
        "march_full": "march_full",
        "no_results": "no_results",
        "close": "close_button",
    }

    def __init__(
        self,
        resources=("food",),
        max_marches: int = 3,
        cooldown: float = 300.0,
        timeout: float = 20.0,
        march_wait: float = 2.0,
        templates=None,
        threshold: float | None = None,
        error_cooldown: float = 60.0,
    ) -> None:
        selected = as_string_list(resources, "resources")
        unknown = set(selected) - set(RESOURCES)
        if unknown:
            raise ValueError(f"unknown resources: {', '.join(sorted(unknown))}")
        self.resources = tuple(selected)
        self.max_marches = as_positive_int(max_marches, "max_marches")
        self.cooldown = as_non_negative_float(cooldown, "cooldown")
        self.timeout = as_positive_float(timeout, "timeout")
        self.march_wait = as_non_negative_float(march_wait, "march_wait")
        super().__init__(resolve_templates(self.TEMPLATES, templates), threshold, error_cooldown)
        self._marches = 0
        self._resource_index = 0

    def phase_start(self, bot) -> None:
        self._marches = 0
        self._resource_index = 0
        self.enter("to_world")

    def phase_to_world(self, bot) -> float | None:
        if self.find(bot, self.t("search")):
            self.enter("open_search")
            return None
        if self.tap(bot, self.t("world")):
            self.enter("open_search")
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_open_search(self, bot) -> float | None:
        if self.find(bot, self.t("search_confirm")):
            self.enter("choose_resource")
            return None
        if self.tap(bot, self.t("search")):
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_choose_resource(self, bot) -> float | None:
        if not self.find(bot, self.t("search_confirm")):
            if self.find(bot, self.t("search")):
                self.enter("open_search")
                return None
            if self.timed_out(bot, self.timeout):
                return None
            return bot.poll_interval
        resource = self.resources[self._resource_index % len(self.resources)]
        if self.tap(bot, self.t(resource)):
            self._resource_index += 1
            self.enter("confirm_search")
            return 1.0
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_confirm_search(self, bot) -> float | None:
        if self.tap(bot, self.t("search_confirm")):
            self.enter("wait_results")
            return 2.0
        if self.find(bot, self.t("tile")):
            self.enter("open_tile")
            return None
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_wait_results(self, bot) -> float | None:
        if self.find_optional(bot, self.t("no_results")):
            logger.info("gather: no resources found")
            return self.complete(self.cooldown)
        if self.find_optional(bot, self.t("march_full")):
            logger.info("gather: all march slots are busy")
            return self.complete(self.cooldown)
        if self.tap(bot, self.t("tile")):
            self.enter("open_tile")
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_open_tile(self, bot) -> float | None:
        if self.tap(bot, self.t("gather")):
            self.enter("march_screen")
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_march_screen(self, bot) -> float | None:
        if self.find_optional(bot, self.t("march_full")):
            logger.info("gather: all march slots are busy")
            return self.complete(self.cooldown)
        if self.tap(bot, self.t("march")):
            self._marches += 1
            self.enter("launched")
            return self.march_wait
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_launched(self, bot) -> float | None:
        if self._marches >= self.max_marches:
            return self.complete(self.cooldown)
        self.enter("open_search")
        return self.march_wait
