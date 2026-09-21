"""Command line entry point."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from typesafe_sdk import TypeSafeClient, TypeSafeError

from jevscan.judge import Judgment, find_candidates, judge_post
from jevscan.posts import SuperXError, fetch_posts


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="jevscan",
        description="Find posts about TypeSafe AI's Jev in your X account, using Jev to judge them.",
    )
    parser.add_argument("--type", dest="post_type", default="all", choices=["posts", "replies", "all"])
    parser.add_argument("--limit", type=int, default=None, help="Maximum posts to read from X (default: all).")
    parser.add_argument("--since", help="UTC ISO-8601 lower bound, e.g. 2026-09-01T00:00:00Z.")
    parser.add_argument("--until", help="UTC ISO-8601 upper bound.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Minimum probability that a post is about Jev before it is reported (default: 0.5).",
    )
    parser.add_argument("--model", default=None, help="Model override (default: the SDK default, jev-latest).")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text report.")
    return parser.parse_args(argv)


def _render(judgments: list[Judgment], threshold: float, scanned: int, candidates: int) -> str:
    matches = [j for j in judgments if j.is_match(threshold)]
    lines = [
        f"Scanned {scanned} post(s); {candidates} mentioned a candidate term; "
        f"{len(matches)} are about TypeSafe AI's Jev (p >= {threshold}).",
    ]
    for judgment in sorted(matches, key=lambda j: j.about_jev, reverse=True):
        post = judgment.post
        lines.append("")
        lines.append(f"  [{judgment.about_jev:.2f}] {judgment.angle} (depth {judgment.depth:.1f})")
        lines.append(f"  {post.posted_at or 'unknown date'}  {post.url or post.id}")
        lines.append(f"  {post.text.strip()[:280]}")

    rejected = [j for j in judgments if not j.is_match(threshold)]
    if rejected:
        lines.append("")
        lines.append(f"Ruled out {len(rejected)} post(s) that matched a term but are not about Jev:")
        for judgment in rejected:
            lines.append(f"  [{judgment.about_jev:.2f}] {judgment.post.text.strip()[:100]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        posts = fetch_posts(post_type=args.post_type, limit=args.limit, since=args.since, until=args.until)
    except SuperXError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    candidates = find_candidates(posts)
    if not candidates:
        print(f"Scanned {len(posts)} post(s); none mentioned Jev, TypeSafe, or System One.")
        return 0

    try:
        with TypeSafeClient() as client:
            judgments = [judge_post(client, post, model=args.model) for post in candidates]
    except TypeSafeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "scanned": len(posts),
            "candidates": len(candidates),
            "threshold": args.threshold,
            "judgments": [
                {**dataclasses.asdict(j), "is_match": j.is_match(args.threshold)}
                for j in judgments
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(_render(judgments, args.threshold, len(posts), len(candidates)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
