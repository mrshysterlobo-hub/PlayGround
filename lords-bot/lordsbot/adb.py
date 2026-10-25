from __future__ import annotations

import re
import shutil
import subprocess
import time

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class AdbError(RuntimeError):
    pass


class Adb:
    def __init__(self, serial: str | None = None, adb_path: str = "adb", timeout: float = 20.0) -> None:
        self.adb_path = adb_path
        self.serial = serial
        self.timeout = timeout
        if shutil.which(adb_path) is None:
            raise AdbError(f"adb executable not found: {adb_path}")

    def _base(self, use_serial: bool = True) -> list[str]:
        command = [self.adb_path]
        if use_serial and self.serial:
            command += ["-s", self.serial]
        return command

    def _run(
        self,
        args: list[str],
        timeout: float | None = None,
        binary: bool = False,
        use_serial: bool = True,
    ) -> subprocess.CompletedProcess:
        command = self._base(use_serial) + args
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=not binary,
                timeout=timeout or self.timeout,
                check=True,
            )
        except FileNotFoundError as exc:
            raise AdbError(f"adb executable not found: {self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"adb command timed out: {' '.join(command)}") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            detail = (stderr or "").strip() or f"exit code {exc.returncode}"
            raise AdbError(f"adb command failed: {' '.join(command)}: {detail}") from exc

    def version(self) -> str:
        output = self._run(["version"], timeout=10, use_serial=False).stdout
        return output.splitlines()[0].strip()

    def devices(self) -> list[str]:
        output = self._run(["devices"], timeout=10, use_serial=False).stdout
        return self.parse_devices(output)

    @staticmethod
    def parse_devices(output: str) -> list[str]:
        serials: list[str] = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith(("List of devices", "*")):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serials.append(parts[0])
        return serials

    def resolve_serial(self) -> str:
        if self.serial:
            available = self.devices()
            if self.serial not in available:
                listed = ", ".join(available) or "none"
                raise AdbError(f"device {self.serial!r} is not available; connected devices: {listed}")
            return self.serial
        available = self.devices()
        if not available:
            raise AdbError("no adb devices found; enable USB debugging and authorize this computer")
        if len(available) > 1:
            raise AdbError("multiple adb devices connected; set device.serial to one of: " + ", ".join(available))
        self.serial = available[0]
        return self.serial

    def connect(self, address: str) -> None:
        output = self._run(["connect", address], timeout=30, use_serial=False).stdout
        if "connected" not in output.lower():
            raise AdbError(f"could not connect to {address}: {output.strip()}")
        self.serial = address

    def shell(self, *args: str, timeout: float | None = None) -> str:
        return self._run(["shell", *args], timeout=timeout).stdout.strip()

    def screencap_png(self, attempts: int = 3) -> bytes:
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                result = self._run(
                    ["exec-out", "screencap", "-p"],
                    timeout=max(self.timeout, 30.0),
                    binary=True,
                )
                data = result.stdout
                if isinstance(data, bytes) and data.startswith(PNG_SIGNATURE) and len(data) > 1024:
                    return data
                last_error = AdbError("screencap returned invalid PNG data")
            except AdbError as exc:
                last_error = exc
            time.sleep(0.5 * (attempt + 1))
        raise AdbError(f"failed to capture screen: {last_error}") from last_error

    def tap(self, x: int, y: int) -> None:
        self.shell("input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.shell(
            "input",
            "swipe",
            str(int(x1)),
            str(int(y1)),
            str(int(x2)),
            str(int(y2)),
            str(int(duration_ms)),
        )

    def keyevent(self, code: str | int) -> None:
        self.shell("input", "keyevent", str(code))

    def wake(self) -> None:
        self.keyevent("KEYCODE_WAKEUP")

    def screen_size(self) -> tuple[int, int]:
        return self.parse_wm_size(self.shell("wm", "size"))

    @staticmethod
    def parse_wm_size(output: str) -> tuple[int, int]:
        override = re.search(r"Override size:\s*(\d+)x(\d+)", output)
        physical = re.search(r"Physical size:\s*(\d+)x(\d+)", output)
        match = override or physical
        if match is None:
            raise AdbError(f"could not parse 'wm size' output: {output!r}")
        return int(match.group(1)), int(match.group(2))
