from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import Task
from .flow import FlowTask
from .options import as_non_negative_float, as_string_list

if TYPE_CHECKING:
    from ..config import Config

logger = logging.getLogger("lordsbot")

DEFAULT_ORDER = (
    "guild_help",
    "shield_check",
    "gather",
    "monster_hunt",
    "train_troops",
)


class RotationTask(Task):
    name = "rotation"

    def __init__(
        self,
        config: Config,
        order=None,
        between: float = 2.0,
    ) -> None:
        from . import create_task

        self.order = tuple(as_string_list(order, "order")) if order is not None else DEFAULT_ORDER
        if "rotation" in self.order:
            raise ValueError("rotation cannot include itself")
        if len(set(self.order)) != len(self.order):
            raise ValueError("order must not contain duplicates")
        self.between = as_non_negative_float(between, "between")
        self._tasks: list[FlowTask] = []
        for name in self.order:
            options = config.tasks.get(name, {})
            child = create_task(name, options)
            if not isinstance(child, FlowTask):
                raise TypeError(f"{name!r} cannot run inside rotation")
            self._tasks.append(child)
        if not self._tasks:
            raise ValueError("rotation requires at least one task")
        self._index = 0

    def step(self, bot) -> float | None:
        for _ in range(len(self._tasks)):
            task = self._tasks[self._index]
            if task.is_complete():
                self._advance()
                continue
            delay = task.step(bot)
            if task.is_complete():
                logger.info("rotation: %s finished, moving to next task", task.name)
                self._advance()
                return self.between
            return delay
        waits = [task.remaining_cooldown() for task in self._tasks if task.remaining_cooldown() > 0]
        if waits:
            return min(waits) + 0.5
        return bot.poll_interval

    def _advance(self) -> None:
        self._index = (self._index + 1) % len(self._tasks)
