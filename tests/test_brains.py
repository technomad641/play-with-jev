import json
import random
from collections import deque

import httpx2
import pytest
from typesafe_sdk import TypeSafeClient

from jevsnake.brains import QUESTIONS, JevBrain, describe, greedy_brain, random_brain
from jevsnake.cli import play
from jevsnake.game import RIGHT, TURNS, Game, MoveInfo, View


def _answer(choice: str):
    return {
        "model": "jev-1.13",
        "usage": {"input_tokens": 90, "output_tokens": 1},
        "answers": {
            "move": {
                "type": "choice",
                "choice": choice,
                "confidence": 0.91,
                "probabilities": {t: (0.91 if t == choice else 0.045) for t in TURNS},
            }
        },
    }


def _client(handler):
    return TypeSafeClient(api_key="test-key", transport=httpx2.MockTransport(handler))


def _decide_from_state(state: dict) -> str:
    """Play using ONLY the fields we send Jev — proves the state is sufficient."""
    moves = state["moves"]
    safe = [t for t, m in moves.items() if m["leads_into"] not in ("wall", "body")]
    roomy = [t for t in safe if moves[t]["reachable_cells_after"] >= state["snake_length"]]
    return max(
        roomy or safe or list(moves),
        key=lambda t: (
            moves[t]["leads_into"] == "food",
            moves[t]["gets_closer_to_food"],
            moves[t]["reachable_cells_after"],
        ),
    )


# ---------- baselines ----------

def test_greedy_never_walks_into_a_wall_when_it_has_a_choice():
    game = Game(width=6, height=6, seed=1)
    game.snake = deque([(5, 3), (4, 3)])
    game.direction = RIGHT
    assert greedy_brain(game.view()) != "straight"


def test_greedy_takes_the_food_when_it_is_adjacent():
    game = Game(seed=1)
    game.food = (game.head[0] + 1, game.head[1])
    assert greedy_brain(game.view()) == "straight"


def test_greedy_turns_away_from_food_when_the_food_sits_in_a_dead_end():
    view = View(
        moves={
            "left": MoveInfo(contains="empty", open_space=3, toward_food=True),
            "straight": MoveInfo(contains="empty", open_space=60, toward_food=False),
            "right": MoveInfo(contains="wall", open_space=0, toward_food=False),
        },
        food_distance=3,
        length=10,
    )
    assert greedy_brain(view) == "straight"


def test_greedy_keeps_chasing_food_when_every_move_is_cramped():
    """Measured, not assumed: treating "all cramped" as a reason to stop chasing food and just
    take the roomiest move scored ~13% worse over 25 seeds. The snake stalls rather than eating
    its way back out, so food still wins the tie-break once no option has room to spare."""
    view = View(
        moves={
            "left": MoveInfo(contains="empty", open_space=4, toward_food=True),
            "straight": MoveInfo(contains="empty", open_space=7, toward_food=False),
            "right": MoveInfo(contains="body", open_space=0, toward_food=False),
        },
        food_distance=2,
        length=20,
    )
    assert greedy_brain(view) == "left"


def test_greedy_still_eats_when_the_food_is_adjacent_and_safe():
    view = View(
        moves={
            "left": MoveInfo(contains="empty", open_space=60, toward_food=False),
            "straight": MoveInfo(contains="food", open_space=59, toward_food=True),
            "right": MoveInfo(contains="empty", open_space=60, toward_food=False),
        },
        food_distance=1,
        length=5,
    )
    assert greedy_brain(view) == "straight"


def test_greedy_survives_far_longer_than_random():
    greedy_scores = [play(Game(seed=s), greedy_brain).score for s in range(4)]
    rng = random.Random(0)
    random_scores = [play(Game(seed=s), lambda v: random_brain(v, rng)).score for s in range(4)]
    assert sum(greedy_scores) > sum(random_scores)


def test_random_returns_a_legal_turn():
    view = Game(seed=1).view()
    assert random_brain(view, random.Random(0)) in TURNS


# ---------- the Jev brain ----------

def test_describe_sends_one_entry_per_turn_with_the_facts_a_turn_depends_on():
    state = describe(Game(seed=1).view())
    assert set(state["moves"]) == set(TURNS)
    for move in state["moves"].values():
        assert set(move) == {"leads_into", "reachable_cells_after", "gets_closer_to_food"}
    assert {"snake_length", "distance_to_food"} <= set(state)


def test_the_question_offers_exactly_the_three_turns():
    assert set(QUESTIONS["move"].criteria) == set(TURNS)
    assert QUESTIONS["move"].type == "choice"


def test_jev_brain_sends_the_expected_request_and_uses_the_answer():
    captured = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json=_answer("left"))

    game = Game(seed=1)
    with _client(handler) as client:
        turn = JevBrain(client)(game.view())

    assert turn == "left"
    assert captured["url"] == "https://api.typesafe.ai/v1/systemone"
    assert captured["body"]["model"] == "jev-latest"
    assert set(captured["body"]["questions"]) == {"move"}
    assert set(captured["body"]["state"]["moves"]) == set(TURNS)


def test_jev_brain_records_latency_per_decision():
    with _client(lambda r: httpx2.Response(200, json=_answer("straight"))) as client:
        brain = JevBrain(client)
        view = Game(seed=1).view()
        brain(view)
        brain(view)
    assert len(brain.latencies) == 2
    assert all(latency >= 0 for latency in brain.latencies)


def test_jev_brain_counts_a_choice_that_would_kill_the_snake():
    game = Game(width=6, height=6, seed=1)
    game.snake = deque([(5, 3), (4, 3)])
    game.direction = RIGHT  # straight is the wall
    with _client(lambda r: httpx2.Response(200, json=_answer("straight"))) as client:
        brain = JevBrain(client)
        assert brain(game.view()) == "straight"
        assert brain.fatal_choices == 1


def test_api_failure_falls_back_to_greedy_instead_of_crashing():
    game = Game(width=6, height=6, seed=1)
    game.snake = deque([(5, 3), (4, 3)])
    game.direction = RIGHT

    with _client(lambda r: httpx2.Response(500, json={"error": "nope"})) as client:
        brain = JevBrain(client)
        turn = brain(game.view())

    assert brain.fallbacks == 1
    assert brain.latencies == []
    assert turn != "straight"  # greedy took over and avoided the wall


def test_model_override_is_passed_through():
    captured = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json=_answer("straight"))

    with _client(handler) as client:
        JevBrain(client, model="jev-1.13")(Game(seed=1).view())

    assert captured["body"]["model"] == "jev-1.13"


def test_a_whole_game_plays_through_the_real_sdk_path():
    """End to end: game -> state -> SDK request -> response -> turn, for every tick."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        state = json.loads(request.content)["state"]
        return httpx2.Response(200, json=_answer(_decide_from_state(state)))

    with _client(handler) as client:
        brain = JevBrain(client)
        game = play(Game(seed=7), brain, max_ticks=600)

    assert game.score > 5
    assert brain.fatal_choices == 0
    assert brain.fallbacks == 0
    assert len(brain.latencies) == game.ticks
