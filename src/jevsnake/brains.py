"""The three things that can steer the snake."""

from __future__ import annotations

import random
from time import perf_counter

from typesafe_sdk import Choice, TypeSafeClient, TypeSafeError

from jevsnake.game import TURNS, Turn, View

QUESTIONS = {
    "move": Choice(
        instructions=(
            "You are steering the snake in a game of Snake. Choose the next turn. "
            "A move that leads into a wall or into the snake's own body ends the game immediately, "
            "so never choose one while another option survives. "
            "Among the moves that survive, prefer the one that gets closer to the food — unless it "
            "leaves fewer reachable cells than the snake is long, which means the snake is about to "
            "seal itself into a pocket it cannot escape. In that case take the roomier move instead."
        ),
        criteria={
            "left": "Turn ninety degrees to the left of the current heading.",
            "straight": "Carry on in the current heading.",
            "right": "Turn ninety degrees to the right of the current heading.",
        },
    ),
}


def describe(view: View) -> dict:
    """The board, reduced to the facts a turn actually depends on."""
    return {
        "snake_length": view.length,
        "distance_to_food": view.food_distance,
        "moves": {
            turn: {
                "leads_into": info.contains,
                "reachable_cells_after": info.open_space,
                "gets_closer_to_food": info.toward_food,
            }
            for turn, info in view.moves.items()
        },
    }


def random_brain(view: View, rng: random.Random | None = None) -> Turn:
    """The floor: no judgment at all."""
    return (rng or random).choice(TURNS)


def greedy_brain(view: View) -> Turn:
    """Plain code, no model: survive, head for food, do not seal yourself in."""
    safe = view.safe_turns()
    if not safe:
        return "straight"
    # Room is a ranking key, not a veto. Treating "no move has room to spare" as a reason to stop
    # chasing food scored ~13% worse over 25 seeds: the snake stalls instead of eating its way out.
    return max(
        safe,
        key=lambda t: (
            view.moves[t].open_space >= view.length,
            view.moves[t].contains == "food",
            view.moves[t].toward_food,
            view.moves[t].open_space,
        ),
    )


class JevBrain:
    """One Choice question per tick. Latency is the whole point, so it stays a single question."""

    def __init__(self, client: TypeSafeClient, model: str | None = None) -> None:
        self.client = client
        self.model = model
        self.latencies: list[float] = []
        self.fatal_choices = 0
        self.fallbacks = 0

    def __call__(self, view: View) -> Turn:
        started = perf_counter()
        try:
            response = self.client.system_one(state=describe(view), questions=QUESTIONS, model=self.model)
        except TypeSafeError:
            self.fallbacks += 1
            return greedy_brain(view)
        self.latencies.append(perf_counter() - started)

        turn: Turn = response.choices["move"].choice
        if view.moves[turn].is_fatal:
            self.fatal_choices += 1
        return turn
