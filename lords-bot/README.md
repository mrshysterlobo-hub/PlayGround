# lords-bot

A small, supervised automation framework for Android games, built around ADB screenshots,
OpenCV template matching, and per-task state machines. It was designed against Lords Mobile,
which is Unity-rendered and exposes nothing usable through accessibility or the UI tree.

> **Warning:** Lords Mobile's terms of service prohibit automation and accounts can be banned.
> Use this only on an account you are willing to lose, keep it supervised, and do not use it for
> competitive or social features.

## How it works

```
adb exec-out screencap -p  ->  OpenCV template match  ->  adb shell input tap
```

Every loop captures one frame, runs optional "guard" templates (popups, reconnect dialogs),
then asks the active task for its next action. Coordinates are always taken from the match
center, so nothing is hard-coded to one screen resolution.

## Built-in tasks

| Task | What it does |
| --- | --- |
| `gather` | Searches for resource nodes, sends gathering marches, and repeats up to `max_marches`. |
| `monster_hunt` | Searches for monsters at a chosen level, hunts, and repeats up to `max_hunts`. |
| `train_troops` | Opens the training building, selects a troop type and tier, sets quantity, and trains. |
| `guild_help` | Opens the guild screen and taps Help All or every individual help hand. |
| `shield_check` | Keeps a shield active, using an inventory shield item when it is missing. |
| `rotation` | Runs the other tasks in order, honoring each task's cooldown. |
| `demo_tap` | Taps one template whenever it is visible; useful for calibration. |

All task-specific screen details are template-driven. The defaults below are a starting point:
capture the equivalent screens from your own phone and the tasks work without code changes.

## Requirements

- Linux host with Python 3.10+
- `adb` (`sudo apt install android-tools-adb` on Debian/Ubuntu)
- Android phone with USB debugging enabled, screen unlocked

## Install

```bash
cd lords-bot
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Phone setup

1. Settings -> About phone -> tap **Build number** seven times.
2. Developer options -> enable **USB debugging**.
3. Connect USB, accept the authorization prompt, then confirm:

```bash
adb devices
```

If the device shows as `unauthorized`, replug the cable and accept the prompt. If Linux reports
no permissions, install `android-sdk-platform-tools-common`, replug, and log out/in so the
`plugdev` group applies.

Wireless ADB also works:

```bash
adb pair 192.168.1.50:37123
adb connect 192.168.1.50:5555
```

The bot does not unlock the phone or bypass a PIN. Keep the game in the foreground.

## Running on Termux (no PC)

Termux can run the whole bot on the phone. On Android 11+ it pairs `adb` to itself through
Wireless debugging, so no root and no computer are required. Termux cannot call `screencap` or
`input` directly; the localhost ADB connection is what grants the shell permissions.

1. Install **Termux from F-Droid**, not the Play Store build.
2. Copy the `lords-bot` directory into Termux home. Use `git clone`, or
   `termux-setup-storage` and copy it from Downloads.
3. Install the dependencies:

```bash
cd lords-bot
bash scripts/termux-install.sh
```

Use the script instead of `pip install -e .` because Termux gets NumPy and OpenCV from
`pkg install python-numpy opencv-python`, not from PyPI wheels.

4. Enable Developer options -> **Wireless debugging**. Open **Pair device with pairing code**
   and note the pairing port and six-digit code. Go back one screen to see the connection port.
5. Pair and connect:

```bash
bash scripts/termux-connect.sh
```

The script asks for the pairing port, code, and connection port. On later runs you normally only
need the connection port; pairing persists.

6. Start the bot from Termux, then switch to the game during the countdown:

```bash
bash scripts/termux-run.sh run --task rotation --dry-run --once --start-delay 10
bash scripts/termux-run.sh run --task rotation --max-runtime 3600 --start-delay 10
```

`termux-run.sh` holds a wake lock so Android does not suspend the bot when you switch back to
the game. Keep the game in the foreground for the whole run.

Termux notes:

- Wireless debugging needs an associated Wi-Fi network, but not working internet. A phone
  hotspot without internet also works.
- Wireless debugging disables on reboot and the connection port changes each time it is enabled.
  Re-run `scripts/termux-connect.sh` after a reboot; pairing does not need to be repeated.
- The connection can drop when the screen locks or the phone sleeps. Disable battery
  optimization for Termux and keep the screen on while running.
- `scripts/termux-connect.sh` can disable the phantom process killer on Android 12L+ and keep
  the screen awake while charging; both are optional prompts.
- On a phone, start with `poll_interval: 1.5` and tune from there.
- If `adb devices` shows more than one entry, set `device.serial` to the `127.0.0.1:<port>`
  value. Leave it `null` for a single device because the port changes between sessions.
- A dry run still captures screenshots through ADB, so it is a good connection test.

## First run

```bash
cp config.example.yaml config.yaml
lordsbot doctor
lordsbot shot -o screenshots/home.png
```

`doctor` verifies adb, the device, the screenshot path, and every template. `shot` saves the
current frame so you can crop templates from it.

## Templates

Crop small, distinctive UI elements from a screenshot at the phone's native resolution and save
them as `templates/<name>.png`. Avoid areas with dynamic text, timers, or resource counts.
16x16 to 200x100 pixels is usually enough.

List the files each task expects, whether each is required or optional, and whether it already
exists:

```bash
lordsbot templates --task gather
lordsbot templates
```

Check your crops against the live screen:

```bash
lordsbot probe
```

Each template is scored with normalized cross-correlation. A score around `0.95+` is solid;
tune `engine.match_threshold` (default `0.88`) if the UI shifts slightly. If your phone
resolution differs from the one used to capture templates, add a matching scale, for example
`scales: [1.0, 0.75]`.

### Shared templates

| File | Meaning |
| --- | --- |
| `world_button` | City button that opens the world map |
| `city_button` | World map button that returns to the city |
| `search_button` | World map search/magnifier |
| `search_confirm` | "Search" button in the search panel |
| `march_button` | Final "March" / "Deploy" button |
| `close_button` | Generic close X, used during recovery |
| `popup_close` | Optional guard template for popups |

### Gather templates

Required: `resource_food`, `resource_wood`, `resource_stone`, `resource_ore`, or `resource_gold`
(only the ones you list in `resources`), plus `resource_tile` and `gather_button`.
Optional: `march_full`, `no_results`.

### Monster hunt templates

Required: `monster_tile`, `hunt_button`, `monster_level_<level>`.
Optional: `monster_tab`, `energy_empty`, `march_full`, `no_results`.

### Training templates

Required: `training_entry`, `troop_infantry`, `tier_1`, `train_start`.
Optional: `train_tab`, `quantity_max`, `quantity_plus`, `train_confirm`, `queue_full`,
`training_marker`.

Use the `templates` override to point at other troop or tier images, for example
`troop_ranged`, `tier_2`, or a localized filename.

### Guild help templates

Required: `guild_button`, `help_hand`.
Optional: `guild_marker`, `help_all`.

### Shield templates

Required: `shield_active`, `items_button`, `shield_item`, `use_button`.
Optional: `use_confirm`.

## Configuration

See `config.example.yaml`. Relative paths are resolved from the current directory.

```yaml
device:
  serial: null          # null = the only connected device
  adb_path: adb

engine:
  poll_interval: 1.0    # seconds between loops
  max_runtime: 0        # 0 = unlimited; prefer a limit
  start_delay: 0        # seconds before the first capture
  dry_run: false
  template_dir: templates
  screenshot_dir: screenshots
  match_threshold: 0.88
  scales: [1.0]
  max_consecutive_failures: 5

guards:
  - template: popup_close
    cooldown: 3

tasks:
  gather:
    resources: [food, wood]
    max_marches: 3
    cooldown: 300
  monster_hunt:
    level: 1
    max_hunts: 3
    energy_cooldown: 900
  train_troops:
    plus_taps: 0
  guild_help:
    empty_grace: 2.0
  shield_check:
    interval: 1800
  rotation:
    order: [guild_help, shield_check, gather, monster_hunt, train_troops]
```

Guards are checked before the task on every loop and are tapped at most once per `cooldown`.
Add one guard per popup or reconnect dialog you need dismissed automatically.

Every task accepts a `templates` mapping that renames any of its template keys, and most accept
`threshold` and `error_cooldown`:

```yaml
tasks:
  gather:
    templates:
      tile: my_resource_node
      gather: my_gather_button
```

### Task options

- `gather`: `resources`, `max_marches`, `cooldown`, `timeout`, `march_wait`
- `monster_hunt`: `level`, `max_hunts`, `cooldown`, `energy_cooldown`, `timeout`, `march_wait`
- `train_troops`: `plus_taps`, `cooldown`, `timeout`
- `guild_help`: `cooldown`, `timeout`, `empty_grace`, `tap_delay`
- `shield_check`: `interval`, `retry`, `timeout`
- `rotation`: `order`, `between`

`plus_taps` is used only when `quantity_max` is unavailable; each tap increases the quantity
slider/plus button once. `empty_grace` is how long the guild screen must show no help requests
before the task backs out. `interval` is how often an active shield is rechecked.

## Task flows

`gather`: ensure world map -> open search -> select resource -> search -> tap a resource tile ->
Gather -> March -> repeat. Stops at `max_marches` or when a march/queue limit is detected.

`monster_hunt`: ensure world map -> open search -> monster tab -> level -> search -> tap a
monster -> Hunt -> March -> repeat. Stops on low energy, no results, or `max_hunts`.

`train_troops`: ensure city -> open training -> troop tab/type -> tier -> quantity (Max, or
`plus_taps`) -> Train -> confirm. Stops when the queue is full.

`guild_help`: open guild -> tap Help All if present, otherwise each help hand -> back. Waits
`empty_grace` for new requests before finishing.

`shield_check`: ensure city -> look for the active shield -> if missing, open items, select the
shield, use it, confirm, and verify. Rechecks every `interval` seconds.

`rotation`: runs tasks in order. When one finishes, its cooldown is skipped by the others; the
rotation sleeps until the next task becomes available.

## Running

Always dry-run first; it logs taps without sending them:

```bash
lordsbot run --task gather --dry-run --once
lordsbot run --task gather --dry-run
lordsbot run --task rotation --dry-run
```

Then run for real with a time limit. On Termux add `--start-delay 10` and switch to the game
after starting the command:

```bash
lordsbot run --task rotation --max-runtime 3600
lordsbot run --task rotation --max-runtime 3600 --start-delay 10
```

Run one task instead if you are still calibrating it:

```bash
lordsbot run --task monster_hunt --max-runtime 1800
```

`demo_tap` taps `templates/world_map.png` whenever it is visible. Press `Ctrl+C` to stop.

## Writing a task

Simple tasks subclass `Task` and implement `step`. Create a module under `lordsbot/tasks/`, then
register it in `lordsbot/tasks/__init__.py`. A step returns the delay in seconds until the next
loop or `None` for the configured poll interval.

```python
import time

from .base import Task


class CollectAll(Task):
    name = "collect_all"

    def __init__(self, template: str, cooldown: float = 30.0) -> None:
        self.template = template
        self.cooldown = cooldown
        self._last = 0.0

    def step(self, bot):
        match = bot.find(self.template)
        if match is not None and time.monotonic() - self._last >= self.cooldown:
            bot.tap_match(match, label="collect")
            self._last = time.monotonic()
            return self.cooldown
        return bot.poll_interval
```

Multi-screen flows should subclass `FlowTask` from `lordsbot/tasks/flow.py`. It provides phase
transitions, timeouts with debug screenshots, optional-template handling, recovery, and cooldowns
(see the built-in tasks for examples).

Useful `Bot` methods in a task:

- `bot.find(name, threshold=None)` returns a `Match` or `None`
- `bot.tap_match(match, label=None)`, `bot.tap(x, y)`, `bot.swipe(...)`, `bot.back()`
- `bot.screen` is the current BGR frame (a NumPy array)
- `bot.save_screenshot(prefix)` writes the current frame for debugging
- `bot.poll_interval`, `bot.dry_run`, `bot.screen_size`

Because this is a state machine, model each screen explicitly: check for the expected template,
tap it, then wait for the next screen instead of assuming a fixed number of taps. That is what
keeps the bot from drifting when a loading screen or popup appears.

## Safety

- Run only while you can watch the phone; stop on the first unexpected behavior.
- Set `max_runtime` even for long sessions.
- Use `--dry-run` after every template or coordinate change.
- Do not automate chat, trading, or anything that affects other players.
- Keep the phone cool and charging; sustained capture plus screen-on drains the battery.

## Tests

```bash
pytest
ruff check .
```
