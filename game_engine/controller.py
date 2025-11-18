from __future__ import annotations
import asyncio
import os
import queue
import sys
import threading
from dataclasses import dataclass
from typing import Callable, Dict, Optional

try:
    import msvcrt  # type: ignore
except ImportError:
    msvcrt = None

if os.name != "nt":  # pragma: no cover - platform guard
    import select
    import termios
    import tty
else:  # pragma: no cover - platform guard
    select = termios = tty = None  # type: ignore


@dataclass
class InputState:
    up: bool = False
    down: bool = False
    left: bool = False
    right: bool = False
    action_a: bool = False
    action_b: bool = False


class Controller:

    def __init__(self) -> None:
        self._queue: "queue.Queue[InputState]" = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._poll_interval = 0.01
        self._saved_mode: Optional[list] = None
        if os.name != "nt" and termios is not None:
            self._enable_raw_mode()
        self._thread.start()

    def _enable_raw_mode(self) -> None:
        fd = sys.stdin.fileno()
        self._saved_mode = termios.tcgetattr(fd)
        tty.setcbreak(fd)

    def close(self) -> None:
        self._stop.set()
        self._queue.put(InputState())
        if self._thread.is_alive():
            self._thread.join(timeout=0.2)
        if termios is not None and self._saved_mode is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._saved_mode)

    async def poll(self) -> InputState:
        while not self._stop.is_set():
            try:
                return self._queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(self._poll_interval)
                break
        return InputState()

    def drain(self) -> list[InputState]:
        drained: list[InputState] = []
        while True:
            try:
                drained.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return drained

    def _reader(self) -> None:
        try:
            if os.name == "nt":
                self._read_windows()
            else:
                self._read_posix()
        except Exception:
            pass

    def _read_windows(self) -> None:
        if msvcrt is None:
            return
        mapping = self.windows_keymap()
        while not self._stop.is_set():
            if not msvcrt.kbhit():
                continue
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                ext = msvcrt.getwch()
                handler = mapping.get(ext)
                if handler:
                    handler(self)
            else:
                handler = self.character_keymap().get(key)
                if handler:
                    handler(self)

    def _read_posix(self) -> None:  # pragma: no cover - system input
        fd = sys.stdin.fileno()
        mapping = self.posix_arrow_map()
        while not self._stop.is_set():
            ready, _, _ = select.select([fd], [], [], 0.01)
            if not ready:
                continue
            char = os.read(fd, 1)
            if not char:
                continue
            if char == b"\x1b":
                seq = os.read(fd, 2)
                if seq.startswith(b"["):
                    handler = mapping.get(seq[1:2])
                    if handler:
                        handler(self)
            else:
                key = char.decode("utf-8", errors="ignore")
                handler = self.character_keymap().get(key)
                if handler:
                    handler(self)

    def windows_keymap(self) -> Dict[str, Callable[["Controller"], None]]:
        return {}

    def posix_arrow_map(self) -> Dict[bytes, Callable[["Controller"], None]]:
        return {}

    def character_keymap(self) -> Dict[str, Callable[["Controller"], None]]:
        return {}

    def emit_state(self, **kwargs: bool) -> None:
        self._queue.put(InputState(**{key: value for key, value in kwargs.items() if value}))


class KeyboardController(Controller):
    def windows_keymap(self) -> Dict[str, Callable[["Controller"], None]]:
        return {
            "H": lambda controller: controller.emit_state(up=True),
            "P": lambda controller: controller.emit_state(down=True),
            "K": lambda controller: controller.emit_state(left=True),
            "M": lambda controller: controller.emit_state(right=True),
        }

    def posix_arrow_map(self) -> Dict[bytes, Callable[["Controller"], None]]:
        return {
            b"A": lambda controller: controller.emit_state(up=True),
            b"B": lambda controller: controller.emit_state(down=True),
            b"D": lambda controller: controller.emit_state(left=True),
            b"C": lambda controller: controller.emit_state(right=True),
        }

    def character_keymap(self) -> Dict[str, Callable[["Controller"], None]]:
        return {
            "/": lambda controller: controller.emit_state(action_a=True),
            "q": lambda controller: controller.emit_state(action_a=True),
            "Q": lambda controller: controller.emit_state(action_a=True),
            "w": lambda controller: controller.emit_state(action_b=True),
            "W": lambda controller: controller.emit_state(action_b=True),
        }
