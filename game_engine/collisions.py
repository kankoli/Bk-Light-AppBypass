from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Tuple

from .sprites import Sprite

Rect = Tuple[float, float, float, float]


@dataclass
class CollisionSystem:
    bounds: Tuple[int, int]

    def within_bounds(self, sprite: Sprite) -> bool:
        x, y, width, height = sprite.bounds
        max_width, max_height = self.bounds
        return 0 <= x <= max_width - width and 0 <= y <= max_height - height

    def clamp(self, sprite: Sprite) -> None:
        x, y, width, height = sprite.bounds
        max_width, max_height = self.bounds
        clamped_x = min(max(x, 0), max_width - width)
        clamped_y = min(max(y, 0), max_height - height)
        sprite.position = (clamped_x, clamped_y)

    def bounce_off_edges(self, sprite: Sprite, restitution: float = 1.0) -> None:
        x, y, width, height = sprite.bounds
        max_width, max_height = self.bounds
        vx, vy = sprite.velocity
        bounced = False
        if x <= 0 and vx < 0:
            vx = -vx * restitution
            bounced = True
        elif x + width >= max_width and vx > 0:
            vx = -vx * restitution
            bounced = True
        if y <= 0 and vy < 0:
            vy = -vy * restitution
            bounced = True
        elif y + height >= max_height and vy > 0:
            vy = -vy * restitution
            bounced = True
        if bounced:
            sprite.velocity = (vx, vy)
            self.clamp(sprite)

    @staticmethod
    def overlaps(a: Sprite, b: Sprite) -> bool:
        ax, ay, aw, ah = a.bounds
        bx, by, bw, bh = b.bounds
        return (ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by)
