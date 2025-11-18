from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple
from PIL import Image, ImageDraw

from bk_light.config import AppConfig, load_config
from bk_light.panel_manager import PanelManager, PanelSession

Rect = Tuple[int, int, int, int]


def _all_tiles(columns: int, rows: int) -> Set[Tuple[int, int]]:
    return {(x, y) for x in range(columns) for y in range(rows)}


@dataclass
class TileDescriptor:
    grid_x: int
    grid_y: int
    session: PanelSession


class DisplaySurface:
    """Virtual canvas backed by the ACT1026 panel layout."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.manager = PanelManager(config)
        self.canvas_size = self.manager.canvas_size
        self.tile_width = config.panels.tile_width
        self.tile_height = config.panels.tile_height
        self.columns = self.manager.columns
        self.rows = self.manager.rows
        self.image = Image.new("RGB", self.canvas_size, (0, 0, 0))
        self._dirty_tiles: Set[Tuple[int, int]] = set()
        self._session_map: dict[Tuple[int, int], PanelSession] = {}
        self._last_clear_color: Tuple[int, int, int] = (0, 0, 0)

    @classmethod
    def from_config(cls, path: Optional[Path] = None) -> "DisplaySurface":
        config = load_config(path)
        return cls(config)

    async def __aenter__(self) -> "DisplaySurface":
        await self.manager.__aenter__()
        self._populate_session_map()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.manager.__aexit__(exc_type, exc, tb)

    def _populate_session_map(self) -> None:
        self._session_map.clear()
        for panel_session in self.manager.sessions:
            descriptor = panel_session.descriptor
            grid_x = descriptor.grid_x if descriptor else 0
            grid_y = descriptor.grid_y if descriptor else 0
            self._session_map[(grid_x, grid_y)] = panel_session

    def clear(self, color: Tuple[int, int, int] = (0, 0, 0)) -> None:
        draw = ImageDraw.Draw(self.image)
        draw.rectangle((0, 0, self.canvas_size[0], self.canvas_size[1]), fill=color)
        self._dirty_tiles = _all_tiles(self.columns, self.rows)
        self._last_clear_color = color

    def fill_rect(self, bbox: Rect, color: Tuple[int, int, int]) -> None:
        draw = ImageDraw.Draw(self.image)
        draw.rectangle(bbox, fill=color)
        self.mark_dirty(bbox)

    def blit_array(self, pixels: Iterable[Iterable[Tuple[int, int, int]]], position: Tuple[int, int]) -> None:
        rows = [list(row) for row in pixels]
        if not rows:
            return
        base_x, base_y = position
        for dy, row in enumerate(rows):
            for dx, color in enumerate(row):
                if color is None:
                    continue
                x = base_x + dx
                y = base_y + dy
                if 0 <= x < self.canvas_size[0] and 0 <= y < self.canvas_size[1]:
                    self.image.putpixel((x, y), color)
        width = max((len(row) for row in rows), default=0)
        height = len(rows)
        bbox = (base_x, base_y, base_x + width, base_y + height)
        self.mark_dirty(bbox)

    def stamp(self, image: Image.Image, position: Tuple[int, int]) -> None:
        self.image.paste(image, position, image if image.mode == "RGBA" else None)
        bbox = (position[0], position[1], position[0] + image.width, position[1] + image.height)
        self.mark_dirty(bbox)

    def mark_dirty(self, bbox: Rect) -> None:
        left, top, right, bottom = bbox
        if right <= left or bottom <= top:
            return
        left_tile = max(0, left // self.tile_width)
        right_tile = min(self.columns - 1, max(0, (right - 1) // self.tile_width))
        top_tile = max(0, top // self.tile_height)
        bottom_tile = min(self.rows - 1, max(0, (bottom - 1) // self.tile_height))
        for gx in range(left_tile, right_tile + 1):
            for gy in range(top_tile, bottom_tile + 1):
                self._dirty_tiles.add((gx, gy))

    async def refresh(self, delay: float = 0.05) -> None:
        if not self._dirty_tiles:
            return
        start = time.perf_counter()
        if not self.manager.multi_panel:
            await self._send_full_frame(delay)
        else:
            await self._send_dirty_tiles(delay)
        elapsed = (time.perf_counter() - start) * 1000
        print(
            f"[DisplaySurface] tiles={len(self._dirty_tiles)} mode={'full' if not self.manager.multi_panel else 'tiles'} elapsed={elapsed:.1f}ms"
        )
        self._dirty_tiles.clear()

    async def _send_full_frame(self, delay: float) -> None:
        buffer = BytesIO()
        self.image.save(buffer, format="PNG", optimize=False)
        session = self.manager.sessions[0].session
        await session.send_png(buffer.getvalue(), delay=delay)

    async def _send_dirty_tiles(self, delay: float) -> None:
        tasks = []
        for tile in self._dirty_tiles:
            panel_session = self._session_map.get(tile)
            if panel_session is None:
                continue
            region = self._tile_region(tile)
            cropped = self.image.crop(region)
            buffer = BytesIO()
            cropped.save(buffer, format="PNG", optimize=False)
            tasks.append(self._timed_send(panel_session, buffer.getvalue(), delay, tile))
        if tasks:
            await asyncio.gather(*tasks)

    async def _timed_send(self, panel_session: PanelSession, payload: bytes, delay: float, tile: Tuple[int, int]) -> None:
        start = time.perf_counter()
        await panel_session.session.send_png(payload, delay=delay)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"[DisplaySurface] tile {tile} write {elapsed:.1f}ms")

    def _tile_region(self, tile: Tuple[int, int]) -> Rect:
        gx, gy = tile
        left = gx * self.tile_width
        top = gy * self.tile_height
        right = left + self.tile_width
        bottom = top + self.tile_height
        return (left, top, right, bottom)

    def as_image(self) -> Image.Image:
        return self.image
