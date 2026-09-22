import pytest

from jevsnake.game import DOWN, LEFT, RIGHT, UP, MoveInfo, View
from jevsnake.human import HumanBrain, turn_towards

ARROWS = {"up": "\x1b[A", "down": "\x1b[B", "right": "\x1b[C", "left": "\x1b[D"}


def _view(heading=RIGHT) -> View:
    empty = MoveInfo(contains="empty", open_space=50, toward_food=False)
    return View(moves=dict.fromkeys(("left", "straight", "right"), empty), food_distance=4, length=3, heading=heading)


@pytest.mark.parametrize("heading,to_left,to_right", [(RIGHT, UP, DOWN), (UP, LEFT, RIGHT), (LEFT, DOWN, UP), (DOWN, RIGHT, LEFT)])
def test_a_key_press_becomes_the_turn_that_reaches_it(heading, to_left, to_right):
    assert turn_towards(heading, to_left) == "left"
    assert turn_towards(heading, to_right) == "right"
    assert turn_towards(heading, heading) == "straight"


@pytest.mark.parametrize("heading", [UP, DOWN, LEFT, RIGHT])
def test_asking_for_a_reversal_is_not_representable_so_it_comes_out_straight(heading):
    """The answer type only has left/straight/right, so a suicidal 180 cannot be expressed —
    the player is protected by exactly the constraint that protects the model."""
    backwards = (-heading[0], -heading[1])
    assert turn_towards(heading, backwards) == "straight"


def test_pressing_nothing_keeps_going():
    assert turn_towards(RIGHT, None) == "straight"


@pytest.mark.parametrize("key,direction", [("w", UP), ("a", LEFT), ("s", DOWN), ("d", RIGHT)])
def test_wasd_steers(key, direction):
    brain = HumanBrain()
    brain._read(key)
    assert brain.desired == direction


@pytest.mark.parametrize("name,direction", [("up", UP), ("down", DOWN), ("left", LEFT), ("right", RIGHT)])
def test_arrow_keys_steer(name, direction):
    brain = HumanBrain()
    brain._read(ARROWS[name])
    assert brain.desired == direction


def test_uppercase_is_accepted():
    brain = HumanBrain()
    brain._read("W")
    assert brain.desired == UP


def test_the_last_key_in_a_burst_wins():
    brain = HumanBrain()
    brain._read(ARROWS["up"] + ARROWS["left"] + "s")
    assert brain.desired == DOWN


def test_q_quits():
    brain = HumanBrain()
    brain._read("q")
    assert brain.quit is True


def test_unknown_keys_are_ignored():
    brain = HumanBrain()
    brain._read("zx9\x1b[Z")
    assert brain.desired is None
    assert brain.quit is False


def test_a_tick_consumes_the_press_so_one_tap_turns_once():
    brain = HumanBrain(tick=0)  # tick=0 means the input window closes immediately
    brain.desired = UP
    assert brain(_view(heading=RIGHT)) == "left"
    assert brain(_view(heading=UP)) == "straight"
