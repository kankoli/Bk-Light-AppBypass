from __future__ import annotations
import asyncio
from typing import List, Sequence

from bk_light.config import load_config

from .controller import Controller, InputState, KeyboardController
from .display import DisplaySurface
from .loop import GameLoop
from .sprites import Sprite


class GameEngine:
    def __init__(self, config_path=None, fps: float = 15.0) -> None:
        self.config_path = config_path
        self.config = load_config(config_path)
        self.surface = DisplaySurface(self.config)
        self.sprites: List[Sprite] = []
        self.controllers: List[Controller] = []
        self.loop = GameLoop(self.surface, self.sprites, self.controllers, fps=fps)
        self.running = True
        self.background_color = (0, 0, 0)
        self._last_drawn: List[tuple[float, float, float, float]] = []

    async def setup(self) -> None:
        pass

    async def handle_inputs(self, inputs: Sequence[InputState], delta: float) -> None:
        pass

    async def update(self, delta: float) -> None:
        for sprite in self.sprites:
            sprite.update(delta)

    async def render(self) -> None:
        if self._last_drawn:
            for bbox in self._last_drawn:
                self.surface.fill_rect(
                    (
                        int(bbox[0]),
                        int(bbox[1]),
                        int(bbox[0] + bbox[2]),
                        int(bbox[1] + bbox[3]),
                    ),
                    self.background_color,
                )
        for sprite in self.sprites:
            sprite.draw(self.surface)
        self._last_drawn = [sprite.bounds for sprite in self.sprites]

    async def _step(self, inputs: Sequence[InputState], delta: float) -> None:
        await self.handle_inputs(inputs, delta)
        await self.update(delta)
        await self.render()

    async def run(self) -> None:
        async with self.surface:
            await self.setup()
            self.surface.clear(self.background_color)
            await self.loop.run(self._step)

    def stop(self) -> None:
        self.loop.stop()
        self.running = False
        for controller in self.controllers:
            close_fn = getattr(controller, "close", None)
            if callable(close_fn):
                close_fn()


class KeyboardGame(GameEngine):
    async def setup(self) -> None:
        await super().setup()
        self.controllers.append(KeyboardController())
