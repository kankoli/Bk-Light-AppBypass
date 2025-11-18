import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from game_engine.demo_space_invaders import SpaceInvadersDemo


def main() -> None:
    game = SpaceInvadersDemo()
    try:
        asyncio.run(game.run())
    except KeyboardInterrupt:
        game.stop()


if __name__ == "__main__":
    main()
