from __future__ import annotations

from typing import Any

from .base import Task
from .demo_tap import DemoTapTask
from .gather import GatherTask
from .guild_help import GuildHelpTask
from .monster_hunt import MonsterHuntTask
from .rotation import RotationTask
from .shield_check import ShieldCheckTask
from .train_troops import TrainTroopsTask

BUILTINS: dict[str, type[Task]] = {
    DemoTapTask.name: DemoTapTask,
    GatherTask.name: GatherTask,
    GuildHelpTask.name: GuildHelpTask,
    MonsterHuntTask.name: MonsterHuntTask,
    RotationTask.name: RotationTask,
    ShieldCheckTask.name: ShieldCheckTask,
    TrainTroopsTask.name: TrainTroopsTask,
}


def task_names() -> list[str]:
    return sorted(BUILTINS)


def task_templates(name: str) -> dict[str, str]:
    task_class = BUILTINS.get(name)
    if task_class is None:
        raise ValueError(f"unknown task {name!r}")
    return dict(getattr(task_class, "TEMPLATES", {}))


def task_optional(name: str) -> frozenset[str]:
    task_class = BUILTINS.get(name)
    if task_class is None:
        raise ValueError(f"unknown task {name!r}")
    return frozenset(getattr(task_class, "OPTIONAL", frozenset()))


def create_task(
    name: str,
    options: dict[str, Any] | None = None,
    config: Any = None,
) -> Task:
    task_class = BUILTINS.get(name)
    if task_class is None:
        available = ", ".join(task_names())
        raise ValueError(f"unknown task {name!r}; available tasks: {available}")
    try:
        if task_class is RotationTask:
            if config is None:
                raise ValueError("rotation requires the full configuration")
            return RotationTask(config=config, **dict(options or {}))
        return task_class(**dict(options or {}))
    except TypeError as exc:
        raise ValueError(f"invalid options for task {name!r}: {exc}") from exc
