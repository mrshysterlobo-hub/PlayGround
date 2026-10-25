from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..bot import Bot


class Task(ABC):
    name = "task"

    @abstractmethod
    def step(self, bot: Bot) -> float | None:
        ...

    def is_complete(self) -> bool:
        return False

    def remaining_cooldown(self) -> float:
        return 0.0
