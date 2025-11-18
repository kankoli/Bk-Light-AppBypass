import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from game_engine.demo import BouncingBallDemo


def main() -> None:
    demo = BouncingBallDemo()
    try:
        asyncio.run(demo.run())
    except KeyboardInterrupt:
        demo.stop()


if __name__ == "__main__":
    main()
