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


class MonsterHuntTask(FlowTask):
    name = "monster_hunt"
    OPTIONAL: ClassVar[frozenset[str]] = frozenset(
        {"monster_tab", "energy", "march_full", "no_results", "close"}
    )

    TEMPLATES: ClassVar[dict[str, str]] = {
        "world": "world_button",
        "search": "search_button",
        "monster_tab": "monster_tab",
        "level": "monster_level_1",
        "search_confirm": "search_confirm",
        "tile": "monster_tile",
        "hunt": "hunt_button",
        "march": "march_button",
        "energy": "energy_empty",
        "march_full": "march_full",
        "no_results": "no_results",
        "close": "close_button",
    }

    def __init__(
        self,
        level: int = 1,
        max_hunts: int = 3,
        cooldown: float = 300.0,
        energy_cooldown: float = 900.0,
        timeout: float = 20.0,
        march_wait: float = 2.0,
        templates=None,
        threshold: float | None = None,
        error_cooldown: float = 60.0,
    ) -> None:
        self.level = as_positive_int(level, "level")
        self.max_hunts = as_positive_int(max_hunts, "max_hunts")
        self.cooldown = as_non_negative_float(cooldown, "cooldown")
        self.energy_cooldown = as_non_negative_float(energy_cooldown, "energy_cooldown")
        self.timeout = as_positive_float(timeout, "timeout")
        self.march_wait = as_non_negative_float(march_wait, "march_wait")
        defaults = dict(self.TEMPLATES)
        defaults["level"] = f"monster_level_{self.level}"
        super().__init__(resolve_templates(defaults, templates), threshold, error_cooldown)
        self._hunts = 0

    def phase_start(self, bot) -> None:
        self._hunts = 0
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
            self.enter("monster_filter")
            return None
        if self.tap(bot, self.t("search")):
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_monster_filter(self, bot) -> float | None:
        self.tap_optional(bot, self.t("monster_tab"))
        self.enter("select_level")
        return 1.0

    def phase_select_level(self, bot) -> float | None:
        self.tap_optional(bot, self.t("level"))
        self.enter("confirm_search")
        return 1.0

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
            logger.info("monster_hunt: no monsters found")
            return self.complete(self.cooldown)
        if self.find_optional(bot, self.t("energy")):
            logger.info("monster_hunt: not enough energy")
            return self.complete(self.energy_cooldown)
        if self.find_optional(bot, self.t("march_full")):
            logger.info("monster_hunt: all march slots are busy")
            return self.complete(self.cooldown)
        if self.tap(bot, self.t("tile")):
            self.enter("open_tile")
            return 1.5
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_open_tile(self, bot) -> float | None:
        if self.tap(bot, self.t("hunt")):
            self.enter("march_screen")
            return 1.5
        if self.find(bot, self.t("march")):
            self.enter("march_screen")
            return None
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_march_screen(self, bot) -> float | None:
        if self.find_optional(bot, self.t("energy")):
            logger.info("monster_hunt: not enough energy")
            return self.complete(self.energy_cooldown)
        if self.find_optional(bot, self.t("march_full")):
            logger.info("monster_hunt: all march slots are busy")
            return self.complete(self.cooldown)
        if self.tap(bot, self.t("march")):
            self._hunts += 1
            self.enter("launched")
            return self.march_wait
        if self.timed_out(bot, self.timeout):
            return None
        return bot.poll_interval

    def phase_launched(self, bot) -> float | None:
        if self._hunts >= self.max_hunts:
            return self.complete(self.cooldown)
        self.enter("open_search")
        return self.march_wait
