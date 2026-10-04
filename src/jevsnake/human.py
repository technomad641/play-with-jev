"""Letting a person drive, so the bot scores have something to be measured against."""

from __future__ import annotations

import os
import select
import sys
import termios
import tty
from contextlib import contextmanager
from time import perf_counter

from jevsnake.game import DOWN, LEFT, RIGHT, UP, Cell, Turn, View, apply_turn

KEYS: dict[str, Cell] = {
    "\x1b[A": UP,
    "\x1b[B": DOWN,
    "\x1b[C": RIGHT,
    "\x1b[D": LEFT,
    "w": UP,
    "s": DOWN,
    "d": RIGHT,
    "a": LEFT,
}


def turn_towards(heading: Cell, desired: Cell | None) -> Turn:
    """Translate a key press into the turn the game accepts.

    Holding the current heading, pressing nothing, or asking for a full reversal all come out as
    "straight" — a reversal is simply not reachable by one left or right turn, so the answer type
    rules it out rather than any validation here.
    """
    if desired is None:
        return "straight"
    for turn in ("left", "right"):
        if apply_turn(heading, turn) == desired:
            return turn
    return "straight"


@contextmanager
def raw_mode(stream=sys.stdin):
    """Read keys the instant they are pressed, without waiting for Enter."""
    descriptor = stream.fileno()
    saved = termios.tcgetattr(descriptor)
    try:
        tty.setcbreak(descriptor)
        yield
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)


class HumanBrain:
    """Holds each tick open for the player, then answers with whatever they last asked for."""

    def __init__(self, tick: float = 0.14) -> None:
        self.tick = tick
        self.desired: Cell | None = None
        self.quit = False

    def __call__(self, view: View) -> Turn:
        self._collect_until(perf_counter() + self.tick)
        turn = turn_towards(view.heading, self.desired)
        self.desired = None
        return turn

    def _collect_until(self, deadline: float) -> None:
        while True:
            remaining = deadline - perf_counter()
            if remaining <= 0 or not select.select([sys.stdin], [], [], remaining)[0]:
                return
            self._read(os.read(sys.stdin.fileno(), 64).decode(errors="ignore"))

    def _read(self, chunk: str) -> None:
        index = 0
        while index < len(chunk):
            sequence = chunk[index : index + 3]
            if sequence in KEYS:
                self.desired = KEYS[sequence]
                index += 3
                continue
            key = chunk[index].lower()
            if key == "q":
                self.quit = True
            elif key in KEYS:
                self.desired = KEYS[key]
            index += 1
