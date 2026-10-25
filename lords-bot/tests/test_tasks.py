from pathlib import Path

from lordsbot.config import Config
from lordsbot.tasks import create_task
from lordsbot.vision import Match


class FakeBot:
    def __init__(self, visible, transitions) -> None:
        self.visible = set(visible)
        self.transitions = transitions
        self.taps: list[str] = []
        self.backs = 0
        self.poll_interval = 0.1

    def find(self, name, threshold=None):
        if name in self.visible:
            return Match(template=name, x=10, y=10, width=4, height=4, score=0.99)
        return None

    def tap_match(self, match, label=None):
        self.taps.append(match.template)
        transition = self.transitions.get(match.template)
        if callable(transition):
            transition(self)
        elif transition is not None:
            self.visible = set(transition)

    def tap(self, x, y, label="tap"):
        self.taps.append(label)

    def back(self):
        self.backs += 1

    def save_screenshot(self, prefix="frame"):
        return Path(f"{prefix}.png")


def run_until_complete(task, bot, limit=200):
    for _ in range(limit):
        task.step(bot)
        if task.is_complete():
            return
    raise AssertionError(f"{task.name} did not complete; taps={bot.taps}")


def test_gather_sends_marches():
    task = create_task("gather", {"resources": ["food"], "max_marches": 2, "cooldown": 10})
    bot = FakeBot(
        {"world_button"},
        {
            "world_button": {"search_button"},
            "search_button": {"search_confirm", "resource_food"},
            "resource_food": {"search_confirm"},
            "search_confirm": {"resource_tile"},
            "resource_tile": {"gather_button"},
            "gather_button": {"march_button"},
            "march_button": {"search_button"},
        },
    )
    run_until_complete(task, bot)
    assert bot.taps == [
        "world_button",
        "search_button",
        "resource_food",
        "search_confirm",
        "resource_tile",
        "gather_button",
        "march_button",
        "search_button",
        "resource_food",
        "search_confirm",
        "resource_tile",
        "gather_button",
        "march_button",
    ]


def test_gather_rotates_resources():
    task = create_task("gather", {"resources": ["food", "wood"], "max_marches": 2})
    bot = FakeBot(
        {"search_button"},
        {
            "search_button": {"search_confirm", "resource_food", "resource_wood"},
            "resource_food": {"search_confirm"},
            "resource_wood": {"search_confirm"},
            "search_confirm": {"resource_tile"},
            "resource_tile": {"gather_button"},
            "gather_button": {"march_button"},
            "march_button": {"search_button"},
        },
    )
    run_until_complete(task, bot)
    assert "resource_food" in bot.taps
    assert "resource_wood" in bot.taps


def test_monster_hunt_stops_when_out_of_energy():
    task = create_task("monster_hunt", {"max_hunts": 1})
    bot = FakeBot(
        {"world_button"},
        {
            "world_button": {"search_button"},
            "search_button": {"search_confirm", "monster_tab"},
            "monster_tab": {"search_confirm", "monster_level_1"},
            "monster_level_1": {"search_confirm"},
            "search_confirm": {"monster_tile"},
            "monster_tile": {"hunt_button"},
            "hunt_button": {"march_button"},
            "march_button": {"search_button"},
        },
    )
    run_until_complete(task, bot)
    assert bot.taps[-1] == "march_button"


def test_monster_hunt_energy_exit():
    task = create_task("monster_hunt", {"max_hunts": 3})
    bot = FakeBot(
        {"search_button"},
        {
            "search_button": {"search_confirm"},
            "search_confirm": {"energy_empty"},
        },
    )
    run_until_complete(task, bot)
    assert "search_confirm" in bot.taps


def test_train_troops_completes():
    task = create_task("train_troops", {"cooldown": 10})
    bot = FakeBot(
        {"training_entry"},
        {
            "training_entry": {"train_tab", "troop_infantry"},
            "train_tab": {"troop_infantry"},
            "troop_infantry": {"tier_1"},
            "tier_1": {"train_start"},
            "train_start": {"train_confirm"},
            "train_confirm": set(),
        },
    )
    run_until_complete(task, bot)
    assert bot.taps == [
        "training_entry",
        "train_tab",
        "troop_infantry",
        "tier_1",
        "train_start",
        "train_confirm",
    ]


def test_shield_check_uses_item():
    task = create_task("shield_check", {"interval": 10, "retry": 5})
    bot = FakeBot(
        {"items_button"},
        {
            "items_button": {"shield_item"},
            "shield_item": {"use_button"},
            "use_button": {"use_confirm"},
            "use_confirm": {"shield_active"},
        },
    )
    run_until_complete(task, bot)
    assert bot.taps == ["items_button", "shield_item", "use_button", "use_confirm"]


def test_shield_check_noop_when_active():
    task = create_task("shield_check", {"interval": 10})
    bot = FakeBot({"shield_active"}, {})
    run_until_complete(task, bot)
    assert bot.taps == []


def test_guild_help_taps_hand():
    task = create_task("guild_help", {"cooldown": 10, "empty_grace": 0})
    bot = FakeBot(
        {"guild_button"},
        {
            "guild_button": {"guild_marker", "help_hand"},
            "help_hand": set(),
        },
    )
    run_until_complete(task, bot)
    assert bot.taps == ["guild_button", "help_hand"]
    assert bot.backs == 1


def test_guild_help_uses_help_all():
    task = create_task("guild_help", {"cooldown": 10, "empty_grace": 0})
    bot = FakeBot(
        {"guild_marker", "help_all"},
        {
            "help_all": set(),
        },
    )
    run_until_complete(task, bot)
    assert bot.taps == ["help_all"]


def test_rotation_moves_on_without_waiting_for_task_cooldown():
    config = Config.from_mapping(
        {
            "tasks": {
                "gather": {"max_marches": 1, "cooldown": 100},
                "rotation": {"order": ["gather"], "between": 0.25},
            }
        }
    )
    task = create_task("rotation", config.tasks["rotation"], config=config)
    bot = FakeBot(
        {"world_button"},
        {
            "world_button": {"search_button"},
            "search_button": {"search_confirm", "resource_food"},
            "resource_food": {"search_confirm"},
            "search_confirm": {"resource_tile"},
            "resource_tile": {"gather_button"},
            "gather_button": {"march_button"},
            "march_button": {"search_button"},
        },
    )
    delays = []
    for _ in range(100):
        delays.append(task.step(bot))
        if bot.taps and bot.taps[-1] == "march_button":
            delays.append(task.step(bot))
            break
    assert 0.25 in delays


def test_rotation_between_gather_and_shield():
    config = Config.from_mapping(
        {
            "tasks": {
                "gather": {"max_marches": 1, "cooldown": 10},
                "shield_check": {"interval": 10},
                "rotation": {"order": ["gather", "shield_check"], "between": 0},
            }
        }
    )
    task = create_task("rotation", config.tasks["rotation"], config=config)
    bot = FakeBot(
        {"world_button"},
        {
            "world_button": {"search_button"},
            "search_button": {"search_confirm", "resource_food"},
            "resource_food": {"search_confirm"},
            "search_confirm": {"resource_tile"},
            "resource_tile": {"gather_button"},
            "gather_button": {"march_button"},
            "march_button": {"items_button"},
            "items_button": {"shield_item"},
            "shield_item": {"use_button"},
            "use_button": {"use_confirm"},
            "use_confirm": {"shield_active"},
        },
    )
    for _ in range(100):
        task.step(bot)
    assert bot.taps == [
        "world_button",
        "search_button",
        "resource_food",
        "search_confirm",
        "resource_tile",
        "gather_button",
        "march_button",
        "items_button",
        "shield_item",
        "use_button",
        "use_confirm",
    ]
