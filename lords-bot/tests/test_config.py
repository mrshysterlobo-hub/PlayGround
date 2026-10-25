import pytest

from lordsbot.config import Config, ConfigError


def test_defaults():
    config = Config.from_mapping({})
    assert config.device.serial is None
    assert config.device.adb_path == "adb"
    assert config.engine.poll_interval == 1.0
    assert config.engine.start_delay == 0.0
    assert config.engine.dry_run is False
    assert config.engine.scales == (1.0,)
    assert config.guards == ()
    assert config.tasks == {}


def test_full_mapping():
    config = Config.from_mapping(
        {
            "device": {"serial": "emulator-5554", "adb_path": "/usr/bin/adb"},
            "engine": {
                "poll_interval": 2,
                "max_runtime": 60,
                "start_delay": 5,
                "dry_run": True,
                "template_dir": "ui",
                "screenshot_dir": "shots",
                "match_threshold": 0.9,
                "scales": [1.0, 0.5],
                "max_consecutive_failures": 2,
            },
            "guards": [
                {"template": "popup_close", "threshold": 0.91, "cooldown": 1.5},
                {"template": "reconnect"},
            ],
            "tasks": {"demo_tap": {"template": "world_map", "cooldown": 3}},
        }
    )
    assert config.device.serial == "emulator-5554"
    assert config.engine.poll_interval == 2.0
    assert config.engine.max_runtime == 60.0
    assert config.engine.start_delay == 5.0
    assert config.engine.dry_run is True
    assert config.engine.scales == (1.0, 0.5)
    assert config.engine.max_consecutive_failures == 2
    assert config.guards[0].threshold == 0.91
    assert config.guards[0].cooldown == 1.5
    assert config.guards[1].threshold is None
    assert config.tasks["demo_tap"]["template"] == "world_map"


def test_unknown_key_rejected():
    with pytest.raises(ConfigError, match="unknown engine keys"):
        Config.from_mapping({"engine": {"poll_intervall": 1}})


def test_unknown_top_level_key_rejected():
    with pytest.raises(ConfigError, match="unknown config keys"):
        Config.from_mapping({"devices": {}})


def test_invalid_threshold():
    with pytest.raises(ConfigError, match="match_threshold"):
        Config.from_mapping({"engine": {"match_threshold": 1.5}})


def test_dry_run_must_be_boolean():
    with pytest.raises(ConfigError, match="dry_run"):
        Config.from_mapping({"engine": {"dry_run": "yes"}})


def test_empty_scales_rejected():
    with pytest.raises(ConfigError, match="scales"):
        Config.from_mapping({"engine": {"scales": []}})


def test_guard_requires_template():
    with pytest.raises(ConfigError, match="template is required"):
        Config.from_mapping({"guards": [{"cooldown": 2}]})


def test_load_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "engine:\n  poll_interval: 0.5\ndevice:\n  serial: phone\n",
        encoding="utf-8",
    )
    config = Config.load(path)
    assert config.engine.poll_interval == 0.5
    assert config.device.serial == "phone"
    assert config.source == path


def test_load_invalid_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("engine: [", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        Config.load(path)


def test_load_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="could not read config"):
        Config.load(tmp_path / "missing.yaml")
