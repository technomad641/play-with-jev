# jevscan

Finds the posts in your X account that are actually about **Jev**, TypeSafe AI's System One
model — and uses Jev itself to decide which ones count.

## Why a model instead of a keyword search

Searching your timeline for `jev` returns the rapper jev., the gaming YouTuber Jev, people named
Jev, and anything containing "type safe". Telling those apart needs semantic understanding, which is
exactly the judgment a System One model is for. So the split is:

- **Code** does the cheap, exact work: pulling posts, matching candidate terms, applying thresholds,
  formatting the report.
- **Jev** does the one thing code cannot: deciding whether a post is about *this* Jev.

## How it works

1. `superx posts:list` pages through your account's posts.
2. A deliberately generous regex keeps any post mentioning `jev*`, `type safe`, or `system one`.
   Over-matching here is free — the next step sorts it out.
3. Each candidate goes to `POST /v1/systemone` as **one request with three parallel questions**
   (independent questions over the same state run together and cannot see each other's answers):
   - `about_jev` — a **Noul**: probability the post is about TypeSafe AI's Jev, with explicit
     `true`/`false` criteria naming the rapper, the YouTuber, and generic "type safety" as the things
     that do *not* count.
   - `angle` — a **Choice** over `launch_news | technical | building | opinion | unrelated`
     (`unrelated` is the no-match outcome).
   - `depth` — a **Score** over a four-level rubric, from a passing mention to a full technical
     write-up.
4. Code filters on the Noul probability against a threshold you control and prints the matches, plus
   what it ruled out and why.

## Setup

```bash
npm install -g superx-cli          # the X data CLI
superx login                       # or: export SUPERX_API_KEY=sxk_...

uv venv && uv pip install -e .
export TYPESAFE_API_KEY=...        # from TypeSafe AI
```

## Usage

```bash
jevscan                                  # scan everything
jevscan --limit 200 --since 2026-09-01T00:00:00Z
jevscan --threshold 0.8                  # only high-probability matches
jevscan --json | jq '.judgments[] | select(.is_match)'
```

Sample output:

```
Scanned 412 post(s); 9 mentioned a candidate term; 4 are about TypeSafe AI's Jev (p >= 0.5).

  [0.97] technical (depth 2.4)
  2026-09-17T14:02:00Z  https://x.com/you/status/...
  Jev returns a typed decision in a single pass...

Ruled out 5 post(s) that matched a term but are not about Jev:
  [0.02] jev just dropped a new album and it is incredible
```

## Tuning

`--threshold` is the dial worth tuning on your own data. The Noul is a calibrated probability, not a
confidence score: 0.5 means Jev finds yes and no about equally likely, not "medium intensity". Run
with `--json` to see the raw probabilities before settling on a cutoff. Typed output guarantees the
shape of the answer, not that it is right — check the ruled-out list on a real scan before trusting
the threshold.

## Development

```bash
.venv/bin/python -m pytest
```

Tests run the real SDK against `httpx2.MockTransport`, so the request body, auth header, endpoint,
and answer parsing are all verified without touching the network.
