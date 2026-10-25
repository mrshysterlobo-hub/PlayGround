import cv2
import numpy as np
import pytest

from lordsbot.vision import Matcher, TemplateError, VisionError, decode_png


def make_image(seed: int, width: int = 400, height: int = 300) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)


def write_template(directory, name: str, image: np.ndarray) -> None:
    assert cv2.imwrite(str(directory / f"{name}.png"), image)


def test_find_returns_center_and_score(tmp_path):
    screen = make_image(1)
    crop = screen[80:110, 100:140].copy()
    write_template(tmp_path, "button", crop)
    matcher = Matcher(tmp_path)
    match = matcher.find(screen, "button")
    assert match is not None
    assert match.center == (120, 95)
    assert match.score > 0.99
    assert (match.width, match.height) == (40, 30)


def test_find_respects_threshold(tmp_path):
    write_template(tmp_path, "button", make_image(1)[80:110, 100:140])
    matcher = Matcher(tmp_path, threshold=0.99)
    assert matcher.find(make_image(2), "button") is None


def test_find_with_scale(tmp_path):
    screen = make_image(3)
    crop = screen[100:140, 200:260].copy()
    write_template(tmp_path, "button", crop)
    small = cv2.resize(screen, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    matcher = Matcher(tmp_path, threshold=0.7, scales=(0.5,))
    match = matcher.find(small, "button")
    assert match is not None
    x, y = match.center
    assert abs(x - 115) <= 2
    assert abs(y - 60) <= 2


def test_flat_template_rejected(tmp_path):
    write_template(tmp_path, "flat", np.zeros((20, 20, 3), dtype=np.uint8))
    matcher = Matcher(tmp_path)
    with pytest.raises(TemplateError, match="contrast"):
        matcher.find(make_image(4), "flat")


def test_missing_template(tmp_path):
    matcher = Matcher(tmp_path)
    with pytest.raises(TemplateError, match="not found"):
        matcher.find(make_image(5), "nope")


def test_template_path_escape(tmp_path):
    (tmp_path / "nested").mkdir()
    matcher = Matcher(tmp_path / "nested")
    with pytest.raises(TemplateError, match="escapes"):
        matcher.find(make_image(6), "../outside")


def test_decode_png_invalid():
    with pytest.raises(VisionError):
        decode_png(b"not a png")


def test_decode_png_roundtrip(tmp_path):
    image = make_image(7, width=32, height=24)
    path = tmp_path / "image.png"
    assert cv2.imwrite(str(path), image)
    decoded = decode_png(path.read_bytes())
    assert decoded.shape == (24, 32, 3)
