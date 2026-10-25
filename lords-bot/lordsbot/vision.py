from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class VisionError(RuntimeError):
    pass


class TemplateError(VisionError):
    pass


@dataclass(frozen=True)
class Match:
    template: str
    x: int
    y: int
    width: int
    height: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


def decode_png(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise VisionError("could not decode screenshot as an image")
    return image


class Matcher:
    def __init__(
        self,
        template_dir: Path | str,
        threshold: float = 0.88,
        scales: Sequence[float] = (1.0,),
        grayscale: bool = True,
    ) -> None:
        self.template_dir = Path(template_dir).resolve()
        if not 0.0 < threshold <= 1.0:
            raise ValueError("match threshold must be in (0, 1]")
        self.threshold = threshold
        self.scales = tuple(float(scale) for scale in scales)
        if not self.scales or any(scale <= 0 for scale in self.scales):
            raise ValueError("scales must be a non-empty list of positive numbers")
        self.grayscale = grayscale
        self._cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def path_for(self, name: str) -> Path:
        candidate = (self.template_dir / name).resolve()
        if candidate.suffix.lower() != ".png":
            candidate = candidate.with_suffix(".png")
        if candidate.parent != self.template_dir and self.template_dir not in candidate.parents:
            raise TemplateError(f"template path escapes the template directory: {name}")
        if not candidate.is_file():
            raise TemplateError(f"template not found: {candidate}")
        return candidate

    def load(self, name: str) -> tuple[np.ndarray, np.ndarray]:
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        path = self.path_for(name)
        template = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if template is None:
            raise TemplateError(f"could not read template image: {path}")
        gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        if float(gray.std()) < 4.0:
            raise TemplateError(
                f"template has too little contrast to match reliably: {path}; crop a distinctive area"
            )
        self._cache[name] = (template, gray)
        return template, gray

    def find(self, screen: np.ndarray, name: str, threshold: float | None = None) -> Match | None:
        if threshold is None:
            threshold = self.threshold
        if screen.ndim == 2:
            haystack = screen
            use_gray = True
        else:
            use_gray = self.grayscale
            haystack = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if use_gray else screen

        template, template_gray = self.load(name)
        needle_base = template_gray if use_gray else template
        screen_height, screen_width = haystack.shape[:2]
        best: Match | None = None

        for scale in self.scales:
            if scale == 1.0:
                needle = needle_base
            else:
                interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                needle = cv2.resize(
                    needle_base,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=interpolation,
                )
            height, width = needle.shape[:2]
            if height > screen_height or width > screen_width:
                continue
            result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
            _, score, _, location = cv2.minMaxLoc(result)
            if not np.isfinite(score):
                continue
            if best is None or score > best.score:
                best = Match(
                    template=name,
                    x=int(location[0]),
                    y=int(location[1]),
                    width=int(width),
                    height=int(height),
                    score=float(score),
                )

        if best is None or best.score < threshold:
            return None
        return best
