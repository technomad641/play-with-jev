# jevsnake

Snake, where every turn is a Jev decision. One `POST /v1/systemone` per tick, for as long as the
snake stays alive.

```bash
jevsnake --brain human        # you drive — no API key needed
jevsnake --brain greedy       # plain code, no API key needed
jevsnake --brain random       # the floor

export TYPESAFE_API_KEY=...
jevsnake                      # Jev drives
```

## Play it yourself first

```bash
jevsnake --brain human
```

Arrow keys or `wasd` to steer, `q` to quit. Do this before watching any bot play — a score of your
own is the only baseline that will actually mean something to you.

## What this is actually demonstrating

**That a model can sit inside a control loop at all.** A normal LLM cannot play Snake tick by tick —
not because it is not smart enough, but because it writes its answer out one token at a time and the
snake would be dead before the sentence finished. Jev returns a decision in one pass, so it can live
in the loop.

The HUD shows `p50` and `p95` decision latency live. That number is the whole point of the project.

## The typed-answer trick

The bot chooses between **`left` / `straight` / `right`** — not `up` / `down` / `left` / `right`.

That's deliberate. With absolute directions, the model could return the direction it came from, which
is an instant 180° death, and your code would have to catch it. With relative turns over a `Choice`
of exactly three options, **an illegal move is not representable in the answer type.** There is no
validation step because there is nothing to validate.

This is the clearest small example of what typed output buys you: you spend your effort describing
the options, not defending against the answer.

It protects the player too. In `--brain human`, pressing the key for the direction you came from
maps to no turn at all, so the snake carries on. That isn't a special case anyone wrote — a reversal
simply cannot be expressed as one `left` or `right`, so there is nothing to guard against. The same
constraint that keeps the model honest keeps you from killing yourself with a stray keypress.

## Who does what

Code computes the facts. Jev makes the judgment. The state sent each tick is just this:

```json
{
  "snake_length": 9,
  "distance_to_food": 4,
  "moves": {
    "left":     {"leads_into": "empty", "reachable_cells_after": 41, "gets_closer_to_food": false},
    "straight": {"leads_into": "food",  "reachable_cells_after": 44, "gets_closer_to_food": true},
    "right":    {"leads_into": "wall",  "reachable_cells_after": 0,  "gets_closer_to_food": false}
  }
}
```

`leads_into` is a lookup. `reachable_cells_after` is a flood fill. `gets_closer_to_food` is
subtraction. None of that needs a model — so none of it uses one. What Jev is asked for is the
trade-off: *take the food, or keep the room?*

It's one question per tick, not three. Independent questions would run in parallel for one round
trip, but in a control loop every token costs latency, and latency is what we're showing off.

## What actually happened when we ran it

Measured against `jev-1.13.0` on 2026-10-04, seed 1, capped at 400 ticks:

| brain | score | outcome | decision p50 | decision p95 | fatal picks |
|---|---|---|---|---|---|
| `jev` | **29** | still alive at the cap | 165 ms | 230 ms | **0** |
| `greedy` | **29** | still alive at the cap | — | — | 0 |
| `random` | 0 | hit a wall on tick 45 | — | — | — |

Then we asked Jev to judge 150 positions from one game and compared each answer against what the
arithmetic would have chosen:

**150 of 150 identical. Zero disagreements. Median confidence 0.97.**

That is a cleaner result than this document originally predicted — it said plain code would beat the
model. It didn't. Jev reproduced the heuristic exactly, which is why the scores match to the point.

**But read what that actually measures.** We handed Jev `leads_into`, `reachable_cells_after` and
`gets_closer_to_food` — all pre-computed — and instructions spelling out the policy in words. So the
answer was already in the input. What we measured is whether the model can apply an explicit rule to
pre-computed facts, quickly and without ever picking a move labelled `wall`. It can: 400 consecutive
decisions, zero fatal picks, and confidence that never dropped below 0.96.

What we did **not** measure is Jev's judgment, because we never asked it to judge anything. Snake is
solvable by arithmetic, and we did the arithmetic ourselves before asking.

For long-run baselines without a tick cap, the offline brains over 25 seeds:

| brain | mean score | best | worst |
|---|---|---|---|
| `greedy` | 61.0 | 89 | 41 |
| `random` | 0.3 | 2 | 0 |
| `human` | play it and find out | — | — |

The demo is the **loop and the latency**, not the strategy. 165 ms per decision is what makes a model
in a control loop possible at all; an LLM writing `{"move": "left"}` token by token could not keep up.
That is the whole point, and it is worth feeling directly rather than being told.

What Jev *is* good at is the same shape of decision when the facts are fuzzy and not computable —
"is this reply rude", "which queue does this ticket belong in", "is this post about the right Jev".
See [`jevscan.md`](jevscan.md) for that version.

## What to watch for

- **`fatal picks`** in the HUD — how often Jev chose a move the state plainly labelled `wall` or
  `body`. Should be zero, and over 400 consecutive live decisions it was. If it isn't, the
  instructions need sharpening, and that's the real lesson of the project: criteria are the code.
- **`api fallbacks`** — ticks where the API failed and the greedy brain covered so the game could
  continue. Non-zero means you're measuring your network, not the model.
- **p95 vs p50** — the tail is what makes a control loop feel broken.

## Options

```
--brain jev|human|greedy|random   who drives (default: jev)
--games N                         play N games and report the spread
--quiet                           no board, just results — use this for comparisons
--seed N                          reproducible food placement
--width / --height                board size (default 20x14)
--min-tick SECONDS                seconds per tick (default 0.14 by hand, 0.06 watching a bot)
--model NAME                      model override (default: jev-latest)
```

`--brain human` needs an interactive terminal, so it refuses to run under `--quiet` or a pipe.

## Development

```bash
.venv/bin/python -m pytest tests/test_game.py tests/test_brains.py
```

The game logic is pure and needs no network. The Jev brain is tested through
`httpx2.MockTransport`, including one test that plays a **whole game** through the real SDK
request/response path, deciding each turn using only the fields we actually send — which proves the
state carries enough information to play.
