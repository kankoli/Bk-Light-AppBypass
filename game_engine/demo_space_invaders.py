from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import List, Sequence

from .collisions import CollisionSystem
from .controller import InputState
from .engine import KeyboardGame
from .sprites import CircleSprite, Sprite, rectangle_pixels


@dataclass
class Bullet(Sprite):
    damage: int = 1


class SpaceInvadersDemo(KeyboardGame):
    def __init__(self, config_path=None, fps: float = 15.0) -> None:
        super().__init__(config_path=config_path, fps=fps)
        width, height = self.surface.canvas_size
        scale = min(width, height) / 32.0
        self.background_color = (2, 2, 8)
        self.collision = CollisionSystem((width, height))
        player_width = max(5, int(5 * scale))
        player_height = max(2, int(2 * scale))
        self.player = Sprite(
            pixel_map=rectangle_pixels(player_width, player_height, (180, 220, 255)),
            position=(width / 2 - player_width / 2, height - (player_height + 2)),
        )
        self.player_speed = 60.0 * scale
        self.bullets: List[Bullet] = []
        self.aliens: List[Sprite] = []
        self.alien_direction = 1
        self.alien_speed = 12.0
        self.alien_drop = 3.0
        self.max_bullets = 3
        self.spawn_wave()
        self.sprites.extend([self.player, *self.aliens])

    async def setup(self) -> None:
        await super().setup()

    def spawn_wave(self) -> None:
        self.aliens.clear()
        width, _ = self.surface.canvas_size
        columns = max(4, width // 8)
        rows = 3
        spacing_x = max(4, width // (columns + 2))
        spacing_y = 4
        colors = [(60, 220, 140), (240, 190, 90), (220, 80, 200)]
        templates = [
            (
                [
                    [0, 1, 0, 1, 0],
                    [1, 1, 1, 1, 1],
                    [0, 1, 1, 1, 0],
                ],
                [
                    [0, 1, 0, 1, 0],
                    [1, 0, 1, 0, 1],
                    [0, 1, 1, 1, 0],
                ],
            ),
            (
                [
                    [1, 0, 1, 0, 1],
                    [1, 1, 1, 1, 1],
                    [0, 1, 0, 1, 0],
                ],
                [
                    [0, 1, 0, 1, 0],
                    [1, 1, 1, 1, 1],
                    [1, 0, 1, 0, 1],
                ],
            ),
        ]
        for row in range(rows):
            for col in range(columns):
                x = 2 + col * spacing_x
                y = 2 + row * spacing_y
                color = colors[row % len(colors)]
                frames = templates[(row + col) % len(templates)]
                pixels = [[color if cell else None for cell in line] for line in frames[0]]
                alien = Sprite(
                    pixel_map=pixels,
                    position=(x, y),
                    velocity=(self.alien_speed * self.alien_direction, 0.0),
                )
                frame_pixels = [
                    [[color if cell else None for cell in line] for line in frame]
                    for frame in frames
                ]
                alien.set_frames(frame_pixels, animation_speed=4, loop=True)
                self.aliens.append(alien)

    def fire_bullet(self) -> None:
        if len(self.bullets) >= self.max_bullets:
            return
        bullet = Bullet(
            pixel_map=rectangle_pixels(1, 2, (255, 255, 255)),
            position=(self.player.position[0] + self.player.size[0] / 2, self.player.position[1] - 3),
            velocity=(0.0, -80.0),
        )
        self.bullets.append(bullet)
        self.sprites.append(bullet)

    async def handle_inputs(self, inputs: Sequence[InputState], delta: float) -> None:
        move = 0.0
        for state in inputs:
            if state.left:
                move -= 1.0
            if state.right:
                move += 1.0
            if state.action_a:
                self.fire_bullet()
        vx = move * self.player_speed
        self.player.velocity = (vx, 0.0)

    async def update(self, delta: float) -> None:
        await super().update(delta)
        self._update_player_bounds()
        self._update_aliens(delta)
        self._update_bullets(delta)
        self._check_collisions()
        if not self.aliens:
            self.spawn_wave()
            self.sprites.extend(self.aliens)

    def _update_player_bounds(self) -> None:
        x, y, width, _ = self.player.bounds
        max_width, _ = self.collision.bounds
        if x < 0:
            self.player.position = (0, y)
        elif x + width > max_width:
            self.player.position = (max_width - width, y)

    def _update_aliens(self, delta: float) -> None:
        flip = False
        max_width, _ = self.collision.bounds
        for alien in self.aliens:
            x, y, width, _ = alien.bounds
            if (x <= 0 and alien.velocity[0] < 0) or (x + width >= max_width and alien.velocity[0] > 0):
                flip = True
        if flip:
            self.alien_direction *= -1
            for alien in self.aliens:
                vx, vy = alien.velocity
                alien.velocity = (self.alien_speed * self.alien_direction, vy)
                alien.position = (alien.position[0], alien.position[1] + self.alien_drop)
        else:
            for alien in self.aliens:
                alien.velocity = (self.alien_speed * self.alien_direction, 0.0)

    def _update_bullets(self, delta: float) -> None:
        max_height = self.collision.bounds[1]
        alive: List[Bullet] = []
        for bullet in self.bullets:
            if bullet.position[1] + bullet.size[1] <= 0:
                if bullet in self.sprites:
                    self.sprites.remove(bullet)
                continue
            alive.append(bullet)
        self.bullets = alive

    def _check_collisions(self) -> None:
        remaining_aliens: List[Sprite] = []
        for alien in self.aliens:
            hit = False
            for bullet in list(self.bullets):
                if self.collision.overlaps(alien, bullet):
                    hit = True
                    if bullet in self.sprites:
                        self.sprites.remove(bullet)
                    self.bullets.remove(bullet)
                    break
            if not hit:
                remaining_aliens.append(alien)
            elif alien in self.sprites:
                self.sprites.remove(alien)
        self.aliens = remaining_aliens
        self._animate_aliens()

    def _animate_aliens(self) -> None:
        for alien in self.aliens:
            frames = getattr(alien, "frames", [alien.pixel_map])
            if len(frames) < 2:
                continue
            alien.animation_phase = (getattr(alien, "animation_phase", 0) + 1) % 20
            frame_index = 0 if alien.animation_phase < 10 else 1
            alien.pixel_map = frames[frame_index]
