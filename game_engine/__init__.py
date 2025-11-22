"""Simple 2D game engine built on top of bk_light."""

from .display import DisplaySurface
from .sprites import Sprite, CircleSprite, rectangle_pixels
from .collisions import CollisionSystem
from .controller import InputState, Controller, KeyboardController
from .loop import GameLoop
from .engine import GameEngine
from .demo import BouncingBallDemo
from .demo_space_invaders import SpaceInvadersDemo
from .demo_snake import SnakeGame
from .demo_tank import TankBattle
from .demo_breakout import BreakoutGame

__all__ = [
    "DisplaySurface",
    "Sprite",
    "CircleSprite",
    "rectangle_pixels",
    "CollisionSystem",
    "InputState",
    "Controller",
    "KeyboardController",
    "GameLoop",
    "GameEngine",
    "BouncingBallDemo",
    "SpaceInvadersDemo",
    "SnakeGame",
    "TankBattle",
    "BreakoutGame",
]
