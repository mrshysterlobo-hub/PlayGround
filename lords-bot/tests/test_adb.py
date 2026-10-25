import pytest

from lordsbot.adb import Adb, AdbError


def test_parse_devices_ignores_header_and_unauthorized():
    output = (
        "List of devices attached\n"
        "R58M12345\tdevice\n"
        "emulator-5554\tdevice\n"
        "ABC123\tunauthorized\n"
        "XYZ789\toffline\n"
        "\n"
    )
    assert Adb.parse_devices(output) == ["R58M12345", "emulator-5554"]


def test_parse_devices_empty():
    assert Adb.parse_devices("List of devices attached\n\n") == []


def test_parse_wm_size_prefers_override():
    output = "Physical size: 1080x2400\nOverride size: 720x1600\n"
    assert Adb.parse_wm_size(output) == (720, 1600)


def test_parse_wm_size_physical_only():
    assert Adb.parse_wm_size("Physical size: 1080x2400\n") == (1080, 2400)


def test_parse_wm_size_invalid():
    with pytest.raises(AdbError):
        Adb.parse_wm_size("garbage")
