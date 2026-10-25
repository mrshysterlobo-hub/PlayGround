from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import numpy as np

from .adb import Adb, AdbError
from .config import Config
from .tasks.base import Task
from .vision import Match, Matcher, VisionError, decode_png

logger = logging.getLogger("lordsbot")


class Bot:
    def __init__(self, config: Config, task: Task) -> None:
        self.config = config
        self.task = task
        self.adb = Adb(config.device.serial, config.device.adb_path)
        self.matcher = Matcher(
            config.engine.template_dir,
            threshold=config.engine.match_threshold,
            scales=config.engine.scales,
        )
        self.screen: np.ndarray | None = None
        self.screen_size = (0, 0)
        self.tick = 0
        self.actions = 0
        self._started = time.monotonic()
        self._guard_last: dict[str, float] = {}

    @property
    def poll_interval(self) -> float:
        return self.config.engine.poll_interval

    @property
    def dry_run(self) -> bool:
        return self.config.engine.dry_run

    def run(self, once: bool = False) -> None:
        serial = self.adb.resolve_serial()
        width, height = self.adb.screen_size()
        self.screen_size = (width, height)
        mode = " (dry run)" if self.dry_run else ""
        logger.info(
            "device %s | screen %dx%d | task %s%s",
            serial,
            width,
            height,
            self.task.name,
            mode,
        )
        if self.config.engine.start_delay > 0:
            logger.info(
                "starting in %.0fs; switch to the game now",
                self.config.engine.start_delay,
            )
            time.sleep(self.config.engine.start_delay)
        self._started = time.monotonic()
        try:
            self._loop(once)
        finally:
            elapsed = time.monotonic() - self._started
            logger.info(
                "stopped after %.0fs | %d ticks | %d actions",
                elapsed,
                self.tick,
                self.actions,
            )

    def _loop(self, once: bool) -> None:
        failures = 0
        max_failures = self.config.engine.max_consecutive_failures
        while True:
            remaining = self._remaining_runtime()
            if remaining is not None and remaining <= 0:
                logger.info("max runtime reached")
                break
            try:
                self.capture()
                failures = 0
                if self._handle_guards():
                    delay = self.poll_interval
                else:
                    result = self.task.step(self)
                    delay = self.poll_interval if result is None else float(result)
            except AdbError as exc:
                failures += 1
                logger.warning("adb failure %d/%d: %s", failures, max_failures, exc)
                if failures >= max_failures:
                    raise
                delay = min(5.0, self.poll_interval * (2**failures))
            if once:
                break
            sleep_for = max(0.05, delay)
            if remaining is not None:
                sleep_for = min(sleep_for, max(0.05, remaining))
            time.sleep(sleep_for)

    def _remaining_runtime(self) -> float | None:
        if not self.config.engine.max_runtime:
            return None
        return self.config.engine.max_runtime - (time.monotonic() - self._started)

    def _handle_guards(self) -> bool:
        now = time.monotonic()
        for guard in self.config.guards:
            last = self._guard_last.get(guard.template, float("-inf"))
            if now - last < guard.cooldown:
                continue
            match = self.find(guard.template, guard.threshold)
            if match is None:
                continue
            self.tap_match(match, label=f"guard:{guard.template}")
            self._guard_last[guard.template] = now
            return True
        return False

    def capture(self) -> np.ndarray:
        self.screen = decode_png(self.adb.screencap_png())
        self.tick += 1
        return self.screen

    def find(self, name: str, threshold: float | None = None) -> Match | None:
        if self.screen is None:
            raise VisionError("no screenshot has been captured yet")
        return self.matcher.find(self.screen, name, threshold)

    def tap_match(self, match: Match, label: str | None = None) -> None:
        x, y = match.center
        self.tap(x, y, label or match.template)

    def tap(self, x: int, y: int, label: str = "tap") -> None:
        x, y = int(x), int(y)
        if self.dry_run:
            logger.info("[dry-run] tap %s at (%d, %d)", label, x, y)
            self.actions += 1
            return
        self.adb.tap(x, y)
        self.actions += 1
        logger.info("tap %s at (%d, %d)", label, x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        if self.dry_run:
            logger.info(
                "[dry-run] swipe (%d, %d) -> (%d, %d) in %dms",
                x1,
                y1,
                x2,
                y2,
                duration_ms,
            )
            self.actions += 1
            return
        self.adb.swipe(x1, y1, x2, y2, duration_ms)
        self.actions += 1
        logger.info("swipe (%d, %d) -> (%d, %d)", x1, y1, x2, y2)

    def back(self) -> None:
        if self.dry_run:
            logger.info("[dry-run] back")
            self.actions += 1
            return
        self.adb.keyevent("KEYCODE_BACK")
        self.actions += 1
        logger.info("back")

    def save_screenshot(self, prefix: str = "frame") -> Path:
        if self.screen is None:
            raise VisionError("no screenshot has been captured yet")
        directory = Path(self.config.engine.screenshot_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = directory / f"{prefix}-{stamp}.png"
        if not cv2.imwrite(str(path), self.screen):
            raise OSError(f"could not write screenshot: {path}")
        return path
