"""Reading posts from an X account through the SuperX CLI."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

MAX_PAGE_SIZE = 100


class SuperXError(RuntimeError):
    """The `superx` CLI was missing, failed, or returned something unreadable."""


@dataclass(frozen=True)
class Post:
    id: str
    text: str
    posted_at: str | None = None
    url: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "Post":
        metrics = raw.get("metrics")
        return cls(
            id=str(raw.get("id", "")),
            text=raw.get("text") or "",
            posted_at=raw.get("posted_at") or raw.get("created_at"),
            url=raw.get("url"),
            metrics=metrics if isinstance(metrics, dict) else {},
        )


def run_superx(args: Sequence[str]) -> Any:
    """Run a `superx` subcommand and decode its JSON stdout."""
    try:
        completed = subprocess.run(
            ["superx", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise SuperXError("The `superx` CLI is not installed. Install it with `npm install -g superx-cli`.") from error

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise SuperXError(f"`superx {' '.join(args)}` failed: {detail}")

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SuperXError(f"`superx {' '.join(args)}` did not return JSON: {completed.stdout[:200]}") from error


def fetch_posts(
    *,
    post_type: str = "all",
    limit: int | None = None,
    since: str | None = None,
    until: str | None = None,
    runner: Callable[[Sequence[str]], Any] = run_superx,
) -> list[Post]:
    """Page through the authenticated account's posts, newest first."""
    posts: list[Post] = []
    page = 1
    while True:
        page_size = MAX_PAGE_SIZE if limit is None else min(MAX_PAGE_SIZE, limit - len(posts))
        if page_size <= 0:
            break

        args = ["posts:list", "--type", post_type, "--sort", "posted_at", "--limit", str(page_size), "--page", str(page)]
        if since:
            args += ["--since", since]
        if until:
            args += ["--until", until]

        payload = runner(args)
        if not isinstance(payload, dict):
            raise SuperXError(f"Expected a JSON object from `superx posts:list`, got {type(payload).__name__}.")
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise SuperXError("`superx posts:list` response had no `data` array.")

        posts.extend(Post.from_api(row) for row in rows if isinstance(row, dict))
        if len(rows) < page_size:
            break
        page += 1

    return posts
