from __future__ import annotations
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from PIL import Image

from .display import DisplaySurface

Color = Tuple[int, int, int]
Pixel = Optional[Color]
PixelMap = List[List[Pixel]]


def rectangle_pixels(width: int, height: int, color: Color) -> PixelMap:
    width = max(1, int(width))
    height = max(1, int(height))
    row: List[Pixel] = [color for _ in range(width)]
    return [list(row) for _ in range(height)]


def invader_pixels(width: int = 5, height: int = 3, color: Color = (60, 220, 120)) -> PixelMap:
    width = max(3, int(width))
    height = max(3, int(height))
    template = [
        "  #  ",
        " ### ",
        "#####",
    ]
    pixels: PixelMap = []
    for row in template:
        pixels.append([(color if ch == "#" else None) for ch in row])
    return pixels


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass
class Sprite:
    pixel_map: PixelMap = field(default_factory=list)
    position: Tuple[float, float] = (0.0, 0.0)
    velocity: Tuple[float, float] = (0.0, 0.0)
    frames: List[PixelMap] = field(default_factory=list)
    animation_speed: float = 0.0
    loop_animation: bool = True
    _last_bounds: Tuple[float, float, float, float] = field(init=False)
    _frame_index: int = field(default=0, init=False)
    _animation_timer: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self._last_bounds = self.bounds

    def update(self, delta: float) -> None:
        self._last_bounds = self.bounds
        x, y = self.position
        vx, vy = self.velocity
        self.position = (x + vx * delta, y + vy * delta)
        self._update_animation(delta)

    @property
    def size(self) -> Tuple[int, int]:
        pixels = self.current_pixels
        if not pixels:
            return (0, 0)
        return (len(pixels[0]), len(pixels))

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        width, height = self.size
        return (self.position[0], self.position[1], width, height)

    @property
    def previous_bounds(self) -> Tuple[float, float, float, float]:
        return self._last_bounds

    def draw(self, surface: DisplaySurface) -> None:
        surface.blit_array(self.current_pixels, (int(self.position[0]), int(self.position[1])))

    def set_velocity(self, speed: float, direction: Tuple[float, float]) -> None:
        dx, dy = direction
        norm = math.hypot(dx, dy) or 1.0
        self.velocity = (speed * dx / norm, speed * dy / norm)

    @property
    def current_pixels(self) -> PixelMap:
        if self.frames:
            index = self._frame_index % len(self.frames)
            return self.frames[index]
        return self.pixel_map

    def set_frames(self, frames: List[PixelMap], animation_speed: float = 0.0, loop: bool = True) -> None:
        filtered = [frame for frame in frames if frame]
        if not filtered:
            return
        self.frames = filtered
        self.animation_speed = animation_speed
        self.loop_animation = loop
        self._frame_index = 0
        self._animation_timer = 0.0

    def load_frames_from_sheet(
        self,
        image_path: Path,
        frame_width: int,
        frame_height: int,
        *,
        columns: Optional[int] = None,
        rows: Optional[int] = None,
        max_frames: Optional[int] = None,
        animation_speed: float = 0.0,
        loop: bool = True,
    ) -> None:
        sheet = Image.open(image_path).convert("RGBA")
        sheet_width, sheet_height = sheet.size
        columns = columns or (sheet_width // frame_width)
        rows = rows or (sheet_height // frame_height)
        frames: List[PixelMap] = []
        for row in range(rows):
            for col in range(columns):
                left = col * frame_width
                top = row * frame_height
                right = left + frame_width
                bottom = top + frame_height
                if right > sheet_width or bottom > sheet_height:
                    continue
                frame_image = sheet.crop((left, top, right, bottom))
                frames.append(self._image_to_pixels(frame_image))
                if max_frames and len(frames) >= max_frames:
                    break
            if max_frames and len(frames) >= max_frames:
                break
        if frames:
            self.set_frames(frames, animation_speed=animation_speed, loop=loop)

    @staticmethod
    def _image_to_pixels(image: Image.Image) -> PixelMap:
        width, height = image.size
        pixels: PixelMap = []
        data = image.load()
        for y in range(height):
            row: List[Pixel] = []
            for x in range(width):
                r, g, b, a = data[x, y]
                if a == 0:
                    row.append(None)
                else:
                    row.append((r, g, b))
            pixels.append(row)
        return pixels

    def _update_animation(self, delta: float) -> None:
        if not self.frames or self.animation_speed <= 0:
            return
        frame_duration = 1.0 / self.animation_speed if self.animation_speed > 0 else 0
        if frame_duration == 0:
            return
        self._animation_timer += delta
        while self._animation_timer >= frame_duration:
            self._animation_timer -= frame_duration
            self._frame_index += 1
            if self._frame_index >= len(self.frames):
                if self.loop_animation:
                    self._frame_index = 0
                else:
                    self._frame_index = len(self.frames) - 1
                    self.animation_speed = 0
                    break


@dataclass
class CircleSprite(Sprite):
    radius: int = field(default=5)
    color: Color = field(default=(255, 255, 255))

    def __post_init__(self) -> None:
        self.radius = int(clamp(self.radius, 1, 64))
        diameter = self.radius * 2
        pixels: PixelMap = []
        for y in range(diameter):
            row: List[Pixel] = []
            for x in range(diameter):
                distance = math.hypot(x - self.radius, y - self.radius)
                if distance <= self.radius:
                    row.append(self.color)
                else:
                    row.append(None)
            pixels.append(row)
        self.pixel_map = pixels
        super().__post_init__()

    def trim_background(self) -> None:
        return
