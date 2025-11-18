from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Deque, List, Sequence
from collections import deque

from .collisions import CollisionSystem
from .controller import InputState
from .engine import KeyboardGame
from .sprites import Sprite, rectangle_pixels


@dataclass
class SnakeSegment(Sprite):
    pass


@dataclass
class Food(Sprite):
    pass


class SnakeGame(KeyboardGame):
    def __init__(self, config_path=None, fps: float = 15.0) -> None:
        super().__init__(config_path=config_path, fps=fps)
        width, height = self.surface.canvas_size
        self.collision = CollisionSystem((width, height))
        self.cell_size = max(2, int(min(width, height) / 20))
        self.direction = (1, 0)
        self.pending_direction = self.direction
        self.grow_pending = 0
        self.snake: Deque[SnakeSegment] = deque()
        self.food: Food | None = None
        self.background_color = (2, 2, 2)
        self._build_snake()
        self._spawn_food()
        self.sprites.extend(list(self.snake))
        if self.food:
            self.sprites.append(self.food)

    def _build_snake(self) -> None:
        head = SnakeSegment(
            pixel_map=rectangle_pixels(self.cell_size, self.cell_size, (80, 220, 80)),
            position=(self.cell_size * 2, self.cell_size * 2),
            velocity=(0.0, 0.0),
        )
        self.snake.appendleft(head)
        for i in range(1, 4):
            segment = SnakeSegment(
                pixel_map=rectangle_pixels(self.cell_size, self.cell_size, (60, 200, 60)),
                position=(self.cell_size * (2 - i), self.cell_size * 2),
                velocity=(0.0, 0.0),
            )
            self.snake.append(segment)

    def _spawn_food(self) -> None:
        width, height = self.surface.canvas_size
        max_x = width // self.cell_size - 1
        max_y = height // self.cell_size - 1
        occupied = {(int(seg.position[0] // self.cell_size), int(seg.position[1] // self.cell_size)) for seg in self.snake}
        while True:
            cell = (random.randint(0, max_x), random.randint(0, max_y))
            if cell not in occupied:
                break
        x = cell[0] * self.cell_size
        y = cell[1] * self.cell_size
        food = Food(
            pixel_map=random.choice(self._fruit_shapes()),
            position=(x, y),
        )
        self.food = food

    async def setup(self) -> None:
        await super().setup()

    async def handle_inputs(self, inputs: Sequence[InputState], delta: float) -> None:
        for state in inputs:
            if state.left and self.direction != (1, 0):
                self.pending_direction = (-1, 0)
            elif state.right and self.direction != (-1, 0):
                self.pending_direction = (1, 0)
            elif state.up and self.direction != (0, 1):
                self.pending_direction = (0, -1)
            elif state.down and self.direction != (0, -1):
                self.pending_direction = (0, 1)

    async def update(self, delta: float) -> None:
        self.direction = self.pending_direction
        dx, dy = self.direction
        head = self.snake[0]
        step = self.cell_size / 2
        new_x = head.position[0] + dx * step
        new_y = head.position[1] + dy * step
        width, height = self.surface.canvas_size
        # wrap around
        new_x %= width
        new_y %= height
        new_head = SnakeSegment(
            pixel_map=rectangle_pixels(self.cell_size, self.cell_size, (80, 220, 80)),
            position=(new_x, new_y),
        )
        # collide with body
        for segment in list(self.snake)[:-1]:
            if (int(segment.position[0]), int(segment.position[1])) == (int(new_x), int(new_y)):
                self._reset()
                return
        self.snake.appendleft(new_head)
        self.sprites.append(new_head)
        # food
        if self.food and self._overlaps(new_x, new_y, self.food):
            self.grow_pending += 2
            if self.food in self.sprites:
                self.sprites.remove(self.food)
            self._spawn_food()
            if self.food:
                self.sprites.append(self.food)
        if self.grow_pending > 0:
            self.grow_pending -= 1
        else:
            tail = self.snake.pop()
            if tail in self.sprites:
                self.sprites.remove(tail)

    def _reset(self) -> None:
        for seg in list(self.snake):
            if seg in self.sprites:
                self.sprites.remove(seg)
        if self.food and self.food in self.sprites:
            self.sprites.remove(self.food)
        self.snake.clear()
        self.food = None
        self.direction = (1, 0)
        self.pending_direction = self.direction
        self.grow_pending = 0
        self._build_snake()
        self._spawn_food()
        self.sprites.extend(list(self.snake))
        if self.food:
            self.sprites.append(self.food)

    def _fruit_shapes(self) -> List[List[List[tuple | None]]]:
        palette = {
            "Y": (255, 240, 0),        # bright yellow
            "y": (230, 210, 0),        # darker yellow
            "R": (220, 30, 60),        # deep red
            "r": (255, 70, 110),       # pink/red
            "G": (40, 180, 80),        # bright green
            "g": (30, 140, 50),        # dark green
            "P": (200, 40, 60),        # deep magenta
            "p": (240, 90, 120),       # light magenta
            "O": (230, 120, 20),       # orange
            "W": (250, 220, 80),       # pale yellow (corn)
            "B": (60, 220, 140),       # teal accent
            "b": (50, 200, 180),       # light teal
            "t": (200, 0, 0),          # tomato red
            "s": (120, 60, 20),        # brown stem
            "u": (255, 255, 255),      # white highlight
            "U": (220, 220, 220),      # soft white
            "h": (180, 140, 100),      # light brown
            "V": (140, 70, 200),       # deep purple
            "v": (190, 120, 230),      # light purple
        }
        def shape(pattern: List[str]) -> List[List[tuple | None]]:
            rows: List[List[tuple | None]] = []
            for line in pattern:
                row: List[tuple | None] = []
                for ch in line:
                    if ch == " ":
                        row.append(None)
                    else:
                        row.append(palette.get(ch, None))
                rows.append(row)
            return rows

        banana = shape([
            "   s   ",
            "  Y     ",
            "  Y     ",
            " YY     ",
            "YYY     ",
            "YYYY    ",
            " YYYYYs ",
            "  ssss  ",
        ])
        pineapple = shape([
            "ggG Ggg",
            "  GGG  ",
            "ys G sy",
            "sYs sYs",
            "ysYsYsy",
            "sYsYsYs",
            "ysYsYsy",
            " ysysy ",
        ])
        watermelon = shape([
            " GgGgG ",
            "GgGgGgG",
            "GgGgGgG",
            "GgGgGgG",
            "GgGgGgG",
            " GgGgG ",
        ])
        pear = shape([
            "  s gg",
            "   Y  ",
            "  YYY ",
            "  YYY ",
            " YYYYs",
            " YYYYs",
            " YYYss",
            "  sss ",
        ])
        plum = shape([
            "gg s ",
            "  s  ",
            " ppp ",
            "pUppP",
            "ppppP",
            "ppppP",
            "pppPP",
            " PPP ",
        ])
        apple = shape([
            " gg s  ",
            "  gs   ",
            " t  Rt ",
            "tUUtttR",
            "tUttttR",
            "ttttttR",
            "ttttURR",
            " ttRRR ",
        ])
        return [banana, pineapple, watermelon, pear, plum, apple]

    def _overlaps(self, x: float, y: float, sprite: Sprite) -> bool:
        return (
            x < sprite.position[0] + sprite.size[0]
            and x + self.cell_size > sprite.position[0]
            and y < sprite.position[1] + sprite.size[1]
            and y + self.cell_size > sprite.position[1]
        )
