"""Play Snake with Jev at the wheel — or take the wheel yourself."""

from __future__ import annotations

import argparse
import contextlib
import random
import sys
import time
from collections.abc import Callable, Iterator

from typesafe_sdk import TypeSafeClient, TypeSafeError

from jevsnake.brains import JevBrain, greedy_brain, random_brain
from jevsnake.game import Game, Turn, View
from jevsnake.human import HumanBrain, raw_mode
from jevsnake.render import HIDE_CURSOR, HOME, SHOW_CURSOR, frame, percentile

Brain = Callable[[View], Turn]

CONTROLS = "arrow keys or wasd to steer · q to quit"


def play(
    game: Game,
    brain: Brain,
    *,
    on_tick: Callable[[Game], None] | None = None,
    max_ticks: int = 100_000,
    stop: Callable[[], bool] | None = None,
) -> Game:
    while game.alive and game.ticks < max_ticks and not (stop and stop()):
        game.step(brain(game.view()))
        if on_tick:
            on_tick(game)
    return game


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jevsnake", description="Snake, steered by Jev one decision at a time.")
    parser.add_argument("--brain", default="jev", choices=["jev", "human", "greedy", "random"])
    parser.add_argument("--width", type=int, default=20)
    parser.add_argument("--height", type=int, default=14)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--model", default=None, help="Model override (default: the SDK default, jev-latest).")
    parser.add_argument("--games", type=int, default=1, help="Play this many games and report the spread.")
    parser.add_argument("--max-ticks", type=int, default=2000)
    parser.add_argument("--quiet", action="store_true", help="No board, just the result. Use this for comparisons.")
    parser.add_argument(
        "--min-tick",
        type=float,
        default=None,
        help="Seconds per tick (default: 0.14 playing by hand, 0.06 watching a bot).",
    )
    return parser.parse_args(argv)


@contextlib.contextmanager
def _terminal(active: bool) -> Iterator[None]:
    """Raw keys and a hidden cursor, only while a person is actually playing."""
    if not active:
        yield
        return
    with raw_mode():
        print(HIDE_CURSOR, end="", flush=True)
        try:
            yield
        finally:
            print(SHOW_CURSOR, end="", flush=True)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    rng = random.Random(args.seed)
    human = args.brain == "human"
    tick = args.min_tick if args.min_tick is not None else (0.14 if human else 0.06)

    if human and (args.quiet or not sys.stdin.isatty()):
        print("error: --brain human needs an interactive terminal and cannot be used with --quiet.", file=sys.stderr)
        return 1

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
    quit_early = False

    try:
        with _terminal(human):
            for game_number in range(args.games):
                seed = None if args.seed is None else args.seed + game_number
                game = Game(width=args.width, height=args.height, seed=seed)

                jev = JevBrain(client, model=args.model) if client is not None else None
                player = HumanBrain(tick=tick) if human else None
                if jev is not None:
                    brain: Brain = jev
                elif player is not None:
                    brain = player
                elif args.brain == "greedy":
                    brain = greedy_brain
                else:
                    brain = lambda view: random_brain(view, rng)  # noqa: E731

                def draw(current: Game) -> None:
                    notes = CONTROLS if human else ""
                    if jev is not None and (jev.fatal_choices or jev.fallbacks):
                        notes = f"fatal picks {jev.fatal_choices}  api fallbacks {jev.fallbacks}"
                    print(HOME + frame(current, args.brain, jev.latencies if jev else [], notes), flush=True)
                    if not human:  # a human brain already spent the tick waiting for a key
                        time.sleep(tick)

                if not args.quiet:
                    draw(game)
                play(
                    game,
                    brain,
                    on_tick=None if args.quiet else draw,
                    max_ticks=args.max_ticks,
                    stop=None if player is None else (lambda: player.quit),
                )

                scores.append(game.score)
                if jev is not None:
                    latencies += jev.latencies
                    fatal += jev.fatal_choices
                    fallbacks += jev.fallbacks
                if args.quiet:
                    print(f"game {game_number + 1}: score {game.score} in {game.ticks} ticks — {game.cause}")
                if player is not None and player.quit:
                    quit_early = True
                    break
    except KeyboardInterrupt:
        quit_early = True
    finally:
        if client is not None:
            client.close()

    if quit_early and not scores:
        return 0
    if args.games > 1 or args.quiet:
        print(f"\n{args.brain}: {len(scores)} game(s), mean score {sum(scores) / len(scores):.1f}, best {max(scores)}")
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
