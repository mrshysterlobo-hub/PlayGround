from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

from .adb import Adb, AdbError
from .bot import Bot
from .config import Config, ConfigError
from .tasks import create_task, task_names, task_optional, task_templates
from .vision import Matcher, TemplateError, VisionError, decode_png

logger = logging.getLogger("lordsbot")


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-c",
        "--config",
        help="path to the YAML config (defaults to config.yaml when present)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lordsbot",
        description="ADB and OpenCV automation for Android games",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="check adb, device, screen, and templates")
    _add_common(doctor)
    doctor.set_defaults(func=cmd_doctor)

    shot = subparsers.add_parser("shot", help="save a screenshot from the device")
    _add_common(shot)
    shot.add_argument("-o", "--output", help="output PNG path")
    shot.set_defaults(func=cmd_shot)

    probe = subparsers.add_parser("probe", help="score every template against the current screen")
    _add_common(probe)
    probe.set_defaults(func=cmd_probe)

    templates = subparsers.add_parser("templates", help="list the template files each task needs")
    _add_common(templates)
    templates.add_argument("--task", choices=task_names(), help="show one task only")
    templates.set_defaults(func=cmd_templates)

    run = subparsers.add_parser(
        "run",
        help=f"run a task loop ({', '.join(task_names())})",
    )
    _add_common(run)
    run.add_argument("--task", required=True, help="task name from the task registry")
    run.add_argument("--dry-run", action="store_true", help="log actions without touching the device")
    run.add_argument("--max-runtime", type=float, help="stop after this many seconds")
    run.add_argument(
        "--start-delay",
        type=float,
        help="wait this many seconds before the first capture",
    )
    run.add_argument("--once", action="store_true", help="capture and act only once")
    run.set_defaults(func=cmd_run)

    return parser


def _load_config(args: argparse.Namespace) -> Config:
    if args.config:
        path = Path(args.config)
        if not path.is_file():
            raise ConfigError(f"config not found: {path}")
        return Config.load(path)
    default = Path("config.yaml")
    if default.is_file():
        return Config.load(default)
    return Config()


def _matcher(config: Config) -> Matcher:
    return Matcher(
        config.engine.template_dir,
        threshold=config.engine.match_threshold,
        scales=config.engine.scales,
    )


def cmd_doctor(args: argparse.Namespace) -> int:
    config = _load_config(args)
    adb = Adb(config.device.serial, config.device.adb_path)
    print(f"adb: {adb.version()}")
    devices = adb.devices()
    print(f"devices: {', '.join(devices) or 'none'}")
    serial = adb.resolve_serial()
    print(f"using: {serial}")
    model = adb.shell("getprop", "ro.product.model")
    print(f"model: {model}")
    width, height = adb.screen_size()
    print(f"screen: {width}x{height}")
    png = adb.screencap_png()
    print(f"screencap: {len(png)} bytes")

    screenshot_dir = Path(config.engine.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    output = screenshot_dir / "doctor.png"
    output.write_bytes(png)
    print(f"saved: {output}")

    matcher = _matcher(config)
    template_root = matcher.template_dir
    templates = sorted(
        (path for path in template_root.glob("**/*.png") if path.is_file()),
        key=lambda path: path.relative_to(template_root).as_posix(),
    ) if template_root.is_dir() else []
    print(f"templates: {len(templates)} in {template_root}")
    for path in templates:
        name = path.relative_to(template_root).as_posix()
        try:
            matcher.load(name)
        except TemplateError as exc:
            print(f"  BAD {name}: {exc}")
        else:
            print(f"  ok  {name}")
    return 0


def cmd_shot(args: argparse.Namespace) -> int:
    config = _load_config(args)
    adb = Adb(config.device.serial, config.device.adb_path)
    adb.resolve_serial()
    png = adb.screencap_png()
    if args.output:
        output = Path(args.output)
    else:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        output = Path(config.engine.screenshot_dir) / f"shot-{stamp}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(png)
    print(output)
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    config = _load_config(args)
    adb = Adb(config.device.serial, config.device.adb_path)
    adb.resolve_serial()
    screen = decode_png(adb.screencap_png())
    matcher = _matcher(config)
    root = matcher.template_dir
    templates = sorted(
        (path for path in root.glob("**/*.png") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    ) if root.is_dir() else []
    if not templates:
        print(f"no templates found in {root}")
        return 0
    print(f"screen: {screen.shape[1]}x{screen.shape[0]} | threshold: {matcher.threshold:.2f}")
    print(f"{'template':40} {'score':>6}  {'center':>13}  result")
    for path in templates:
        name = path.relative_to(root).as_posix()
        try:
            match = matcher.find(screen, name, threshold=0.0)
        except TemplateError as exc:
            print(f"{name:40} {'-':>6}  {'-':>13}  BAD: {exc}")
            continue
        if match is None:
            print(f"{name:40} {'-':>6}  {'-':>13}  no match")
            continue
        center = f"({match.center[0]},{match.center[1]})"
        verdict = "PASS" if match.score >= matcher.threshold else "low"
        print(f"{name:40} {match.score:6.3f}  {center:>13}  {verdict}")
    return 0


def cmd_templates(args: argparse.Namespace) -> int:
    config = _load_config(args)
    root = Path(config.engine.template_dir)
    names = [args.task] if args.task else task_names()
    for name in names:
        mapping = task_templates(name)
        optional = task_optional(name)
        print(name)
        if not mapping:
            print("  (no template files)")
            continue
        for key, filename in sorted(mapping.items()):
            path = root / f"{filename}.png"
            status = "ok" if path.is_file() else "missing"
            role = "optional" if key in optional else "required"
            print(f"  {key:16} {status:8} {role:8} {path}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = _load_config(args)
    if args.dry_run or args.max_runtime is not None or args.start_delay is not None:
        engine = config.engine
        if args.dry_run:
            engine = replace(engine, dry_run=True)
        if args.max_runtime is not None:
            if args.max_runtime < 0:
                raise ConfigError("--max-runtime must be zero or greater")
            engine = replace(engine, max_runtime=args.max_runtime)
        if args.start_delay is not None:
            if args.start_delay < 0:
                raise ConfigError("--start-delay must be zero or greater")
            engine = replace(engine, start_delay=args.start_delay)
        config = replace(config, engine=engine)

    options = config.tasks.get(args.task, {})
    task = create_task(args.task, options, config=config)
    bot = Bot(config, task)
    bot.run(once=args.once)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except (AdbError, ConfigError, VisionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
