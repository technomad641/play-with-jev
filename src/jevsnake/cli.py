"""Play Snake with Jev at the wheel."""

from __future__ import annotations

import argparse
import random
import sys
import time
from collections.abc import Callable

from typesafe_sdk import TypeSafeClient, TypeSafeError

from jevsnake.brains import JevBrain, greedy_brain, random_brain
from jevsnake.game import Game, Turn, View
from jevsnake.render import HOME, frame, percentile

Brain = Callable[[View], Turn]


def play(game: Game, brain: Brain, *, on_tick: Callable[[Game], None] | None = None, max_ticks: int = 100_000) -> Game:
    while game.alive and game.ticks < max_ticks:
        game.step(brain(game.view()))
        if on_tick:
            on_tick(game)
    return game


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jevsnake", description="Snake, steered by Jev one decision at a time.")
    parser.add_argument("--brain", default="jev", choices=["jev", "greedy", "random"])
    parser.add_argument("--width", type=int, default=20)
    parser.add_argument("--height", type=int, default=14)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--model", default=None, help="Model override (default: the SDK default, jev-latest).")
    parser.add_argument("--games", type=int, default=1, help="Play this many games and report the spread.")
    parser.add_argument("--max-ticks", type=int, default=2000)
    parser.add_argument("--quiet", action="store_true", help="No board, just the result. Use this for comparisons.")
    parser.add_argument("--min-tick", type=float, default=0.06, help="Seconds to hold each drawn frame.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    rng = random.Random(args.seed)

    client = None
    if args.brain == "jev":
        try:
            client = TypeSafeClient()
        except TypeSafeError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    scores: list[int] = []
    latencies: list[float] = []
    fatal = fallbacks = 0

    try:
        for game_number in range(args.games):
            seed = None if args.seed is None else args.seed + game_number
            game = Game(width=args.width, height=args.height, seed=seed)

            jev = JevBrain(client, model=args.model) if client is not None else None
            if jev is not None:
                brain: Brain = jev
            elif args.brain == "greedy":
                brain = greedy_brain
            else:
                brain = lambda view: random_brain(view, rng)  # noqa: E731

            def draw(current: Game) -> None:
                notes = ""
                if jev is not None and (jev.fatal_choices or jev.fallbacks):
                    notes = f"fatal picks {jev.fatal_choices}  api fallbacks {jev.fallbacks}"
                print(HOME + frame(current, args.brain, jev.latencies if jev else [], notes), flush=True)
                time.sleep(args.min_tick)

            play(game, brain, on_tick=None if args.quiet else draw, max_ticks=args.max_ticks)

            scores.append(game.score)
            if jev is not None:
                latencies += jev.latencies
                fatal += jev.fatal_choices
                fallbacks += jev.fallbacks
            if args.quiet:
                print(f"game {game_number + 1}: score {game.score} in {game.ticks} ticks — {game.cause}")
    finally:
        if client is not None:
            client.close()

    if args.games > 1 or args.quiet:
        print(f"\n{args.brain}: {args.games} game(s), mean score {sum(scores) / len(scores):.1f}, best {max(scores)}")
    if latencies:
        print(
            f"decisions {len(latencies)}  "
            f"p50 {percentile(latencies, 0.5) * 1000:.0f}ms  "
            f"p95 {percentile(latencies, 0.95) * 1000:.0f}ms  "
            f"fatal picks {fatal}  api fallbacks {fallbacks}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
