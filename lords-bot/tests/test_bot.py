import cv2
import numpy as np

from lordsbot.bot import Bot
from lordsbot.config import Config
from lordsbot.tasks.base import Task
from lordsbot.vision import Match


class FakeAdb:
    def __init__(self) -> None:
        self.taps: list[tuple[int, int]] = []

    def resolve_serial(self) -> str:
        return "fake-device"

    def screen_size(self) -> tuple[int, int]:
        return (320, 240)

    def screencap_png(self) -> bytes:
        ok, buffer = cv2.imencode(".png", np.zeros((240, 320, 3), dtype=np.uint8))
        assert ok
        return buffer.tobytes()

    def tap(self, x: int, y: int) -> None:
        self.taps.append((x, y))


class TapTask(Task):
    name = "tap"

    def step(self, bot) -> float:
        bot.tap(10, 20, label="test")
        return 0.0


class GuardMatcher:
    def __init__(self, match: Match) -> None:
        self.match = match

    def find(self, screen, name, threshold=None):
        return self.match


def build_bot(monkeypatch, config, task, match=None):
    fake_adb = FakeAdb()
    monkeypatch.setattr("lordsbot.bot.Adb", lambda *args, **kwargs: fake_adb)
    if match is not None:
        matcher = GuardMatcher(match)
        monkeypatch.setattr("lordsbot.bot.Matcher", lambda *args, **kwargs: matcher)
    return Bot(config, task), fake_adb


def test_dry_run_does_not_tap(monkeypatch):
    bot, fake_adb = build_bot(
        monkeypatch,
        Config.from_mapping({"engine": {"dry_run": True}}),
        TapTask(),
    )
    bot.run(once=True)
    assert fake_adb.taps == []
    assert bot.tick == 1
    assert bot.actions == 1


def test_real_run_taps(monkeypatch):
    bot, fake_adb = build_bot(monkeypatch, Config.from_mapping({}), TapTask())
    bot.run(once=True)
    assert fake_adb.taps == [(10, 20)]
    assert bot.actions == 1


def test_guard_runs_before_task(monkeypatch):
    config = Config.from_mapping({"guards": [{"template": "popup", "cooldown": 0}]})
    match = Match(template="popup", x=100, y=100, width=20, height=20, score=0.99)
    bot, fake_adb = build_bot(monkeypatch, config, TapTask(), match=match)
    bot.run(once=True)
    assert fake_adb.taps == [(110, 110)]
    assert bot.actions == 1
