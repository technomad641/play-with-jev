"""Drawing the board to a terminal."""

from __future__ import annotations

from jevsnake.game import Game

HEAD, BODY, FOOD, DIM, RESET = "\033[38;5;45m", "\033[38;5;32m", "\033[38;5;214m", "\033[38;5;244m", "\033[0m"
HOME = "\033[H\033[J"


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def frame(game: Game, brain: str, latencies: list[float], notes: str = "") -> str:
    body = set(game.snake)
    lines = [f"{DIM}┌{'─' * (game.width * 2)}┐{RESET}"]
    for y in range(game.height):
        row = [f"{DIM}│{RESET}"]
        for x in range(game.width):
            cell = (x, y)
            if cell == game.head:
                row.append(f"{HEAD}██{RESET}")
            elif cell in body:
                row.append(f"{BODY}██{RESET}")
            elif cell == game.food:
                row.append(f"{FOOD}██{RESET}")
            else:
                row.append("  ")
        row.append(f"{DIM}│{RESET}")
        lines.append("".join(row))
    lines.append(f"{DIM}└{'─' * (game.width * 2)}┘{RESET}")

    status = f" {brain}  score {game.score}  length {len(game.snake)}  tick {game.ticks}"
    if latencies:
        status += f"  decision p50 {percentile(latencies, 0.5) * 1000:.0f}ms  p95 {percentile(latencies, 0.95) * 1000:.0f}ms"
    lines.append(status)
    if notes:
        lines.append(f"{DIM} {notes}{RESET}")
    if not game.alive:
        lines.append(f" game over — {game.cause}")
    return "\n".join(lines)
