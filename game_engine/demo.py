from __future__ import annotations
import math
from typing import Sequence

from .collisions import CollisionSystem
from .controller import InputState
from .engine import KeyboardGame
from .sprites import CircleSprite, Sprite, rectangle_pixels


class BouncingBallDemo(KeyboardGame):
    def __init__(self, config_path=None, fps: float = 15.0) -> None:
        super().__init__(config_path=config_path, fps=fps)
        width, height = self.surface.canvas_size
        scale = min(width, height) / 32.0
        self.collision = CollisionSystem((width, height))
        radius = max(2, int(2 * scale))
        vx = 12.0 * scale
        vy = 10.0 * scale
        self.ball = CircleSprite(
            pixel_map=[],
            position=(radius * 2.0, radius * 2.0),
            velocity=(vx, vy),
            radius=radius,
            color=(255, 255, 255),
        )
        self.sprites.append(self.ball)
        self._add_scan_line(width)

    def _add_scan_line(self, width: float) -> None:
        pixel = Sprite(pixel_map=rectangle_pixels(1, 1, (255, 50, 50)), position=(0.0, 1.0), velocity=(40.0, 0.0))
        self.scan_pixel = pixel
        self.scan_bounds = (0.0, width)
        self.sprites.append(pixel)

    async def setup(self) -> None:
        await super().setup()

    async def handle_inputs(self, inputs: Sequence[InputState], delta: float) -> None:
        for state in inputs:
            if state.action_a:
                self.ball.velocity = (self.ball.velocity[0] * 1.2, self.ball.velocity[1] * 1.2)
                print(self.ball.velocity)
            if state.action_b:
                self.ball.velocity = (self.ball.velocity[0] * 0.8, self.ball.velocity[1] * 0.8)
                print(self.ball.velocity)
            if state.up:
                self.ball.velocity = (self.ball.velocity[0] + 10, self.ball.velocity[1] + 10)
                print(self.ball.velocity)
            if state.down:
                self.ball.velocity = (self.ball.velocity[0] - 10, self.ball.velocity[1] - 10)
                print(self.ball.velocity)

    async def update(self, delta: float) -> None:
        await super().update(delta)
        self.collision.bounce_off_edges(self.ball, restitution=1.0)
        self._update_scan_pixel(delta)

    def _update_scan_pixel(self, delta: float) -> None:
        pixel = getattr(self, "scan_pixel", None)
        if not pixel:
            return
        min_x, max_x = (0.0, self.surface.canvas_size[0])
        x, y, width, _ = pixel.bounds
        if x <= min_x and pixel.velocity[0] < 0:
            pixel.velocity = (-pixel.velocity[0], 0.0)
        elif x + width >= max_x and pixel.velocity[0] > 0:
            pixel.velocity = (-pixel.velocity[0], 0.0)
