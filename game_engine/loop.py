from __future__ import annotations
import asyncio
import time
from typing import List

from .controller import Controller, InputState
from .display import DisplaySurface
from .sprites import Sprite


class GameLoop:
    def __init__(
        self,
        surface: DisplaySurface,
        sprites: List[Sprite],
        controllers: List[Controller],
        fps: float = 15.0,
    ) -> None:
        self.surface = surface
        self.sprites = sprites
        self.controllers = controllers
        self.fps = fps
        self.running = True

    async def _gather_inputs(self) -> List[InputState]:
        if not self.controllers:
            return [InputState()]
        return await asyncio.gather(*(controller.poll() for controller in self.controllers))

    async def run(self, update_callback) -> None:
        frame_time = 1.0 / max(1.0, self.fps)
        while self.running:
            loop_start = time.perf_counter()
            inputs_start = loop_start
            inputs = await self._gather_inputs()
            inputs_elapsed = (time.perf_counter() - inputs_start) * 1000
            step_start = time.perf_counter()
            await update_callback(inputs, frame_time)
            step_elapsed = (time.perf_counter() - step_start) * 1000
            refresh_start = time.perf_counter()
            await self.surface.refresh(delay=0.005)
            refresh_elapsed = (time.perf_counter() - refresh_start) * 1000
            elapsed = time.perf_counter() - loop_start
            print(
                f"[GameLoop] inputs={inputs_elapsed:.1f}ms update={step_elapsed:.1f}ms refresh={refresh_elapsed:.1f}ms total={elapsed*1000:.1f}ms"
            )
            await asyncio.sleep(max(0.0, frame_time - elapsed))

    def stop(self) -> None:
        self.running = False
