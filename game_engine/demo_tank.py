from __future__ import annotations
import math
import random
from dataclasses import dataclass
from typing import Deque, List, Sequence, Tuple
from collections import deque

from .collisions import CollisionSystem
from .controller import InputState
from .engine import KeyboardGame
from .sprites import Sprite, rectangle_pixels, Color

DIRECTION_VECTORS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

TANK_PATTERN = [
    [0, 0, 1, 0, 0],
    [0, 1, 1, 1, 0],
    [1, 1, 1, 1, 1],
    [1, 0, 1, 0, 1],
    [1, 0, 0, 0, 1],
]


def _rotate_pattern(pattern: List[List[int]]) -> List[List[int]]:
    return [list(row) for row in zip(*pattern[::-1])]


def _pattern_for_direction(direction: Tuple[int, int]) -> List[List[int]]:
    rotations = {
        (0, -1): 0,
        (1, 0): 1,
        (0, 1): 2,
        (-1, 0): 3,
    }
    turns = rotations.get(direction, 0)
    pattern = [row[:] for row in TANK_PATTERN]
    for _ in range(turns):
        pattern = _rotate_pattern(pattern)
    return pattern


def _tank_pixels(color: Color, direction: Tuple[int, int]) -> List[List[Color | None]]:
    pattern = _pattern_for_direction(direction)
    pixels: List[List[Color | None]] = []
    for row in pattern:
        pixels.append([color if cell else None for cell in row])
    return pixels


def _bullet_pixels(direction: Tuple[int, int], color: Color) -> List[List[Color | None]]:
    if direction in [(0, -1), (0, 1)]:
        return rectangle_pixels(1, 3, color)
    return rectangle_pixels(3, 1, color)


@dataclass
class Bullet(Sprite):
    friendly: bool = True


@dataclass
class Tank(Sprite):
    grid_step: int = 4
    facing: Tuple[int, int] = (0, -1)
    color: Color = (255, 255, 255)
    pending_move: int = 0
    move_direction: Tuple[int, int] = (0, 0)


class SolidSprite(Sprite):
    solid: bool = True


class Wall(SolidSprite):
    def __init__(self, position: Tuple[int, int], size: Tuple[int, int], color: Color = (80, 80, 80)) -> None:
        base = rectangle_pixels(size[0], size[1], color)
        self.base_map = base
        self.flash_timer = 0.0
        self.color = color
        super().__init__(pixel_map=base, position=position)

    def register_impact(self, direction: Tuple[int, int]) -> None:
        self.flash_timer = 0.2
        self.flash_direction = direction

    def update(self, delta: float) -> None:
        super().update(delta)
        if self.flash_timer > 0:
            self.flash_timer = max(0.0, self.flash_timer - delta)

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        width = len(self.base_map[0]) if self.base_map else 0
        height = len(self.base_map)
        return (self.position[0], self.position[1], width, height)

    @property
    def current_pixels(self) -> List[List[Color | None]]:
        if self.flash_timer > 0:
            return self._impact_map(getattr(self, "flash_direction", (0, -1)))
        return self.base_map

    def _impact_map(self, direction: Tuple[int, int]) -> List[List[Color | None]]:
        pixels = [row[:] for row in self.base_map]
        width = len(pixels[0]) if pixels else 0
        height = len(pixels)
        highlight = (200, 200, 200)
        if direction == (0, -1):
            for x in range(width):
                pixels[0][x] = highlight
        elif direction == (0, 1):
            for x in range(width):
                pixels[-1][x] = highlight
        elif direction == (-1, 0):
            for y in range(height):
                pixels[y][0] = highlight
        elif direction == (1, 0):
            for y in range(height):
                pixels[y][-1] = highlight
        return pixels


@dataclass
class LifeDisplay(Sprite):
    count: int = 0
    color: Color = (255, 255, 255)

    def __post_init__(self) -> None:
        super().__post_init__()

    def draw(self, surface: DisplaySurface) -> None:
        width = surface.canvas_size[0] - 1
        row_y = 1
        for i in range(max(0, self.count)):
            x = width - i * 2
            if x < 0:
                break
            surface.blit_array([[(self.color)]], (x, row_y))


class TankBattle(KeyboardGame):
    def __init__(self, config_path=None, fps: float = 15.0, respect_walls: bool = True) -> None:
        super().__init__(config_path=config_path, fps=fps)
        width, height = self.surface.canvas_size
        self.collision = CollisionSystem((width, height))
        self.respect_walls = respect_walls
        self.cell = max(4, int(min(width, height) / 32))
        self.player = Tank(
            pixel_map=[],
            position=(width / 2, height - self.cell * 2),
            grid_step=self.cell,
            color=(120, 200, 120),
        )
        self._set_tank_direction(self.player, (0, -1))
        self.bullets: List[Bullet] = []
        self.enemies: List[Tank] = []
        self.enemy_speed = 1
        self.enemy_spawn_points = [
            (self.cell, self.cell),
            (width - self.cell * 2, self.cell),
            (width / 2, self.cell),
        ]
        self.spawn_enemy_delays: Deque[float] = deque()
        self.lives = 3
        self.walls: List[Wall] = []
        self._build_map()
        for _ in range(3):
            self._spawn_enemy(initial=True)
        self.life_display = LifeDisplay()
        self.life_display.count = self.lives
        self.sprites.extend(self.walls)
        self.sprites.extend([self.player, *self.enemies, self.life_display])
        self.surface.clear(self.background_color)

    async def handle_inputs(self, inputs: Sequence[InputState], delta: float) -> None:
        desired_direction: Tuple[int, int] | None = None
        for state in inputs:
            if state.left:
                desired_direction = (-1, 0)
            elif state.right:
                desired_direction = (1, 0)
            elif state.up:
                desired_direction = (0, -1)
            elif state.down:
                desired_direction = (0, 1)
            if state.action_a or state.action_b:
                self._fire_bullet(self.player, friendly=True)
        if desired_direction:
            if desired_direction != self.player.facing:
                self._set_tank_direction(self.player, desired_direction)
            else:
                self._queue_player_move()

    async def update(self, delta: float) -> None:
        self._apply_pending_move(self.player, clamp_top=False)
        await super().update(delta)
        self._update_bullets(delta)
        self._update_enemies(delta)
        self._check_collisions()
        self._process_spawn_queue(delta)
        self._update_life_display()

    def _move_single_pixel(self, tank: Tank, direction: Tuple[int, int], clamp_top: bool) -> None:
        new_x = tank.position[0] + direction[0]
        new_y = tank.position[1] + direction[1]
        width, height = self.surface.canvas_size
        if self.respect_walls:
            new_x = min(max(0, new_x), width - tank.size[0])
            limit_y = height / 2 if clamp_top else height
            new_y = min(max(0, new_y), limit_y - tank.size[1])
            if self._collides_with_walls(new_x, new_y, tank.size):
                new_x, new_y = tank.position
        else:
            new_x %= width
            limit_y = height / 2 if clamp_top else height
            new_y = max(0, min(limit_y - tank.size[1], new_y))
        tank.position = (new_x, new_y)

    def _apply_pending_move(self, tank: Tank, clamp_top: bool) -> None:
        if tank.pending_move > 0:
            self._move_single_pixel(tank, tank.facing, clamp_top)
            tank.pending_move -= 1

    def _fire_bullet(self, tank: Tank, friendly: bool) -> None:
        color = (255, 255, 255) if friendly else (255, 160, 80)
        direction = tank.facing
        bullet_pixels = _bullet_pixels(direction, color)
        width = len(bullet_pixels[0]) if bullet_pixels else 1
        height = len(bullet_pixels)
        if direction == (0, -1):
            origin_x = tank.position[0] + tank.size[0] / 2 - width / 2
            origin_y = tank.position[1] - height
        elif direction == (0, 1):
            origin_x = tank.position[0] + tank.size[0] / 2 - width / 2
            origin_y = tank.position[1] + tank.size[1]
        elif direction == (-1, 0):
            origin_x = tank.position[0] - width
            origin_y = tank.position[1] + tank.size[1] / 2 - height / 2
        else:  # right
            origin_x = tank.position[0] + tank.size[0]
            origin_y = tank.position[1] + tank.size[1] / 2 - height / 2
        velocity = (direction[0] * self.cell * 8, direction[1] * self.cell * 8)
        bullet = Bullet(
            pixel_map=bullet_pixels,
            position=(origin_x, origin_y),
            velocity=velocity,
            friendly=friendly,
        )
        self.bullets.append(bullet)
        self.sprites.append(bullet)

    def _update_bullets(self, delta: float) -> None:
        remaining: List[Bullet] = []
        max_height = self.surface.canvas_size[1]
        for bullet in self.bullets:
            if bullet.position[1] < -5 or bullet.position[1] > max_height + 5:
                if bullet in self.sprites:
                    self.sprites.remove(bullet)
                continue
            hit_wall = self._bullet_hit_wall(bullet)
            if hit_wall:
                continue
            remaining.append(bullet)
        self.bullets = remaining

    def _update_enemies(self, delta: float) -> None:
        for enemy in self.enemies:
            if enemy.pending_move <= 0:
                axis = random.choice(["horizontal", "vertical"])
                if axis == "horizontal":
                    direction = random.choice([(-1, 0), (1, 0)])
                else:
                    direction = random.choice([(0, 1), (0, -1)])
                self._set_tank_direction(enemy, direction)
                enemy.pending_move = self.enemy_speed * self.cell
            if random.random() < 0.03:
                self._fire_bullet(enemy, friendly=False)
            self._apply_pending_move(enemy, clamp_top=True)

    def _check_collisions(self) -> None:
        remaining_enemies: List[Tank] = []
        for enemy in self.enemies:
            hit = False
            for bullet in list(self.bullets):
                if bullet.friendly and self.collision.overlaps(enemy, bullet):
                    hit = True
                    self._schedule_spawn()
                    if bullet in self.sprites:
                        self.sprites.remove(bullet)
                    self.bullets.remove(bullet)
                    break
                if not bullet.friendly and self.collision.overlaps(self.player, bullet):
                    self.lives = max(0, self.lives - 1)
                    self._reset_player()
                    if bullet in self.sprites:
                        self.sprites.remove(bullet)
                    self.bullets.remove(bullet)
                    break
            if not hit:
                remaining_enemies.append(enemy)
            elif enemy in self.sprites:
                self.sprites.remove(enemy)
        self.enemies = remaining_enemies
        if self.lives <= 0:
            self._restart_game()

    def _reset_player(self) -> None:
        width, height = self.surface.canvas_size
        self.player.position = (width / 2, height - self.cell * 2)
        self._set_tank_direction(self.player, (0, -1))
        self.player.pending_move = 0

    def _spawn_enemy(self, initial: bool = False) -> None:
        if not initial and len(self.enemies) >= 6:
            return
        spawn = random.choice(self.enemy_spawn_points)
        direction = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
        enemy = Tank(
            pixel_map=[],
            position=spawn,
            velocity=(0, 0),
            grid_step=self.cell,
            color=(220, 120, 120),
        )
        self._set_tank_direction(enemy, direction)
        enemy.pending_move = self.enemy_speed * self.cell
        self.enemies.append(enemy)
        self.sprites.append(enemy)

    def _schedule_spawn(self) -> None:
        self.spawn_enemy_delays.append(3.0)

    def _process_spawn_queue(self, delta: float) -> None:
        updated = deque()
        while self.spawn_enemy_delays:
            delay = self.spawn_enemy_delays.popleft() - delta
            if delay <= 0:
                self._spawn_enemy()
            else:
                updated.append(delay)
        self.spawn_enemy_delays = updated

    def _queue_player_move(self) -> None:
        self.player.pending_move += self.player.grid_step

    def _bullet_hit_wall(self, bullet: Bullet) -> bool:
        for wall in self.walls:
            if self.collision.overlaps(wall, bullet):
                direction = (
                    0 if bullet.velocity[0] == 0 else int(math.copysign(1, bullet.velocity[0])),
                    0 if bullet.velocity[1] == 0 else int(math.copysign(1, bullet.velocity[1])),
                )
                wall.register_impact(direction)
                if bullet in self.sprites:
                    self.sprites.remove(bullet)
                return True
        return False

    def _collides_with_walls(self, x: float, y: float, size: Tuple[int, int]) -> bool:
        width, height = size
        for wall in self.walls:
            wx, wy, ww, wh = wall.bounds
            if not (x + width <= wx or x >= wx + ww or y + height <= wy or y >= wy + wh):
                return True
        return False

    def _update_life_display(self) -> None:
        self.life_display.count = self.lives

    def _restart_game(self) -> None:
        self.lives = 3
        self.bullets.clear()
        for bullet in list(self.sprites):
            if isinstance(bullet, Bullet) and bullet in self.sprites:
                self.sprites.remove(bullet)
        for enemy in list(self.enemies):
            if enemy in self.sprites:
                self.sprites.remove(enemy)
        self.enemies.clear()
        for _ in range(3):
            self._spawn_enemy()
        self._reset_player()

    def _build_map(self) -> None:
        width, height = self.surface.canvas_size
        tile = 4
        cols = max(1, width // tile)
        rows = max(1, height // tile)
        forbidden = [
            (width / 2, height - self.cell * 2),
            *self.enemy_spawn_points,
        ]
        def near_spawn(x: float, y: float) -> bool:
            for sx, sy in forbidden:
                if abs(x - sx) < tile * 1.5 and abs(y - sy) < tile * 1.5:
                    return True
            return False
        density = 0.1
        for row in range(rows):
            for col in range(cols):
                x = col * tile
                y = row * tile
                if near_spawn(x, y):
                    continue
                if y + tile > height - tile * 4:
                    continue
                if random.random() < density:
                    size = (tile, tile)
                    wall = Wall(position=(x, y), size=size)
                    self.walls.append(wall)

    def _set_tank_direction(self, tank: Tank, direction: Tuple[int, int]) -> None:
        if direction not in {(0, -1), (0, 1), (-1, 0), (1, 0)}:
            return
        tank.facing = direction
        tank.pixel_map = _tank_pixels(tank.color, direction)
        tank.move_direction = direction
