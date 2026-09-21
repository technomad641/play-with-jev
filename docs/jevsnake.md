# jevsnake

Snake, where every turn is a Jev decision. One `POST /v1/systemone` per tick, for as long as the
snake stays alive.

```bash
export TYPESAFE_API_KEY=...
jevsnake                      # Jev drives
jevsnake --brain greedy       # plain code, no API key needed
jevsnake --brain random       # the floor
```

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

## Be honest about the result

**Plain code plays this better than Jev does, and that is fine.**

Snake is solvable. The `greedy` brain is about fifteen lines with no model behind it:

| brain | mean score over 25 seeds | best | worst |
|---|---|---|---|
| `greedy` | **61.0** | 89 | 41 |
| `random` | 0.3 | 2 | 0 |

Run `jevsnake --brain jev --quiet --games 5` and compare. If Jev loses to `greedy`, that is the
expected result, not a bug — the state we hand it already contains the answer, so the model is being
asked to re-derive a conclusion that arithmetic reaches more reliably.

The demo is the **loop and the latency**, not the strategy. Any task where plain code can compute the
right answer is a task that does not need a model; Snake is one of those, and it is worth feeling
that directly rather than being told it.

What Jev *is* good at is the same shape of decision when the facts are fuzzy and not computable —
"is this reply rude", "which queue does this ticket belong in", "is this post about the right Jev".
See [`jevscan.md`](jevscan.md) for that version.

## What to watch for

- **`fatal picks`** in the HUD — how often Jev chose a move the state plainly labelled `wall` or
  `body`. Should be zero. If it isn't, the instructions need sharpening, and that's the real lesson
  of the project: criteria are the code.
- **`api fallbacks`** — ticks where the API failed and the greedy brain covered so the game could
  continue. Non-zero means you're measuring your network, not the model.
- **p95 vs p50** — the tail is what makes a control loop feel broken.

## Options

```
--brain jev|greedy|random   who drives (default: jev)
--games N                   play N games and report the spread
--quiet                     no board, just results — use this for comparisons
--seed N                    reproducible food placement
--width / --height          board size (default 20x14)
--min-tick SECONDS          hold each drawn frame (default 0.06)
--model NAME                model override (default: jev-latest)
```

## Development

```bash
.venv/bin/python -m pytest tests/test_game.py tests/test_brains.py
```

The game logic is pure and needs no network. The Jev brain is tested through
`httpx2.MockTransport`, including one test that plays a **whole game** through the real SDK
request/response path, deciding each turn using only the fields we actually send — which proves the
state carries enough information to play.
