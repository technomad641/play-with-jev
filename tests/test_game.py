from collections import deque

import pytest

from jevsnake.game import DOWN, LEFT, RIGHT, UP, Game, apply_turn


@pytest.mark.parametrize(
    "heading,left,right",
    [(RIGHT, UP, DOWN), (UP, LEFT, RIGHT), (LEFT, DOWN, UP), (DOWN, RIGHT, LEFT)],
)
def test_turns_rotate_the_heading(heading, left, right):
    assert apply_turn(heading, "left") == left
    assert apply_turn(heading, "right") == right
    assert apply_turn(heading, "straight") == heading


def test_moving_forward_keeps_the_snake_the_same_length():
    game = Game(seed=1)
    before = len(game.snake)
    game.step("straight")
    assert len(game.snake) == before
    assert game.alive


def test_eating_grows_the_snake_and_scores():
    game = Game(seed=1)
    game.food = (game.head[0] + 1, game.head[1])
    before = len(game.snake)
    game.step("straight")
    assert game.score == 1
    assert len(game.snake) == before + 1


def test_running_into_the_wall_ends_the_game():
    game = Game(width=6, height=6, seed=1)
    game.snake = deque([(5, 3), (4, 3)])
    game.direction = RIGHT
    game.step("straight")
    assert not game.alive
    assert game.cause == "wall"


def test_running_into_itself_ends_the_game():
    game = Game(seed=1)
    game.snake = deque([(5, 5), (6, 5), (6, 6), (5, 6), (4, 6), (4, 5)])
    game.direction = LEFT
    game.food = (0, 0)
    game.step("left")  # turns DOWN, into its own body at (5, 6)
    assert not game.alive
    assert game.cause == "itself"


def test_the_tail_is_not_an_obstacle_because_it_moves_away():
    game = Game(seed=1)
    game.snake = deque([(5, 5), (4, 5), (4, 6), (5, 6)])
    game.direction = RIGHT
    game.food = (0, 0)
    assert game.view().moves["right"].contains == "empty"
    game.step("right")  # into (5, 6), where the tail was
    assert game.alive
    assert game.head == (5, 6)


def test_the_tail_is_an_obstacle_when_the_snake_is_about_to_grow():
    game = Game(seed=1)
    game.snake = deque([(5, 5), (4, 5), (4, 6), (5, 6)])
    game.direction = RIGHT
    game.food = (6, 5)  # eating on this very move, so nothing is vacated
    game.step("straight")
    assert game.alive and game.score == 1
    assert len(game.snake) == 5


def test_starvation_ends_the_game():
    game = Game(width=6, height=6, seed=1)
    game.ticks_since_food = game.starvation_limit - 1
    game.food = (0, 0)
    game.step("straight")
    assert not game.alive
    assert game.cause == "starved"


def test_view_classifies_each_direction():
    game = Game(width=6, height=6, seed=1)
    game.snake = deque([(5, 3), (4, 3)])
    game.direction = RIGHT
    game.food = (5, 2)
    view = game.view()
    assert view.moves["straight"].contains == "wall"
    assert view.moves["left"].contains == "food"
    assert view.moves["left"].toward_food is True
    assert view.safe_turns() == ["left", "right"]


def test_a_wall_move_has_no_open_space():
    game = Game(width=6, height=6, seed=1)
    game.snake = deque([(5, 3), (4, 3)])
    game.direction = RIGHT
    assert game.view().moves["straight"].open_space == 0


def test_open_space_counts_only_what_is_reachable():
    game = Game(width=7, height=3, seed=1)
    # The body forms a solid column at x=3, cutting the board in two. The head is on the left
    # side, so the nine cells on the right must not be counted as reachable.
    game.snake = deque([(2, 2), (3, 2), (3, 1), (3, 0), (2, 0)])
    game.direction = LEFT
    game.food = (0, 0)

    view = game.view()
    assert view.moves["left"].contains == "wall"  # off the bottom edge
    assert view.moves["straight"].open_space == 8  # the left half only, minus the head
    assert view.moves["straight"].open_space < game.width * game.height - len(game.snake)


def test_step_does_nothing_once_dead():
    game = Game(width=6, height=6, seed=1)
    game.snake = deque([(5, 3), (4, 3)])
    game.direction = RIGHT
    game.step("straight")
    ticks = game.ticks
    game.step("left")
    assert game.ticks == ticks
