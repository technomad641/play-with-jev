"""Snake, as pure logic: no I/O, no model, no rendering."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Literal

Cell = tuple[int, int]
Turn = Literal["left", "straight", "right"]
TURNS: tuple[Turn, ...] = ("left", "straight", "right")

UP, DOWN, LEFT, RIGHT = (0, -1), (0, 1), (-1, 0), (1, 0)


def apply_turn(direction: Cell, turn: Turn) -> Cell:
    dx, dy = direction
    if turn == "left":
        return (dy, -dx)
    if turn == "right":
        return (-dy, dx)
    return direction


@dataclass(frozen=True)
class MoveInfo:
    """What a candidate turn leads into, computed in code."""

    contains: Literal["empty", "wall", "body", "food"]
    open_space: int
    toward_food: bool

    @property
    def is_fatal(self) -> bool:
        return self.contains in ("wall", "body")


@dataclass(frozen=True)
class View:
    """Everything a brain is allowed to know on a given tick."""

    moves: dict[Turn, MoveInfo]
    food_distance: int
    length: int

    def safe_turns(self) -> list[Turn]:
        return [t for t in TURNS if not self.moves[t].is_fatal]


class Game:
    def __init__(self, width: int = 20, height: int = 14, seed: int | None = None) -> None:
        self.width = width
        self.height = height
        self.rng = random.Random(seed)
        mid = (width // 2, height // 2)
        self.snake: deque[Cell] = deque([mid, (mid[0] - 1, mid[1])])
        self.direction: Cell = RIGHT
        self.score = 0
        self.ticks = 0
        self.alive = True
        self.cause: str | None = None
        self.ticks_since_food = 0
        self.food: Cell = self._place_food()

    @property
    def head(self) -> Cell:
        return self.snake[0]

    @property
    def starvation_limit(self) -> int:
        return self.width * self.height * 2

    def _place_food(self) -> Cell:
        free = [
            (x, y)
            for x in range(self.width)
            for y in range(self.height)
            if (x, y) not in self.snake
        ]
        return self.rng.choice(free)

    def _blocked(self, cell: Cell, body: set[Cell]) -> bool:
        x, y = cell
        return not (0 <= x < self.width and 0 <= y < self.height) or cell in body

    def _open_space(self, start: Cell, body: set[Cell]) -> int:
        """How many cells are reachable from `start` — the room a move leaves you."""
        if self._blocked(start, body):
            return 0
        seen = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for step in (UP, DOWN, LEFT, RIGHT):
                nxt = (x + step[0], y + step[1])
                if nxt not in seen and not self._blocked(nxt, body):
                    seen.add(nxt)
                    queue.append(nxt)
        return len(seen)

    def view(self) -> View:
        # The tail vacates as the head advances, so it is not an obstacle unless we grow.
        body_after = set(self.snake) - {self.snake[-1]}
        moves: dict[Turn, MoveInfo] = {}
        for turn in TURNS:
            direction = apply_turn(self.direction, turn)
            target = (self.head[0] + direction[0], self.head[1] + direction[1])
            if not (0 <= target[0] < self.width and 0 <= target[1] < self.height):
                contains = "wall"
            elif target == self.food:
                contains = "food"
            elif target in body_after:
                contains = "body"
            else:
                contains = "empty"
            moves[turn] = MoveInfo(
                contains=contains,
                open_space=self._open_space(target, body_after),
                toward_food=_distance(target, self.food) < _distance(self.head, self.food),
            )
        return View(moves=moves, food_distance=_distance(self.head, self.food), length=len(self.snake))

    def step(self, turn: Turn) -> None:
        if not self.alive:
            return

        self.direction = apply_turn(self.direction, turn)
        head = (self.head[0] + self.direction[0], self.head[1] + self.direction[1])
        self.ticks += 1

        eating = head == self.food
        body = set(self.snake) if eating else set(self.snake) - {self.snake[-1]}
        if self._blocked(head, body):
            self.alive = False
            self.cause = "wall" if not (0 <= head[0] < self.width and 0 <= head[1] < self.height) else "itself"
            return

        self.snake.appendleft(head)
        if eating:
            self.score += 1
            self.ticks_since_food = 0
            if len(self.snake) == self.width * self.height:
                self.alive = False
                self.cause = "filled the board"
                return
            self.food = self._place_food()
        else:
            self.snake.pop()
            self.ticks_since_food += 1
            if self.ticks_since_food >= self.starvation_limit:
                self.alive = False
                self.cause = "starved"


def _distance(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
