import json

import pytest

from jevscan.posts import MAX_PAGE_SIZE, Post, SuperXError, fetch_posts


def _page(count: int, start: int = 0) -> dict:
    return {"data": [{"id": str(i), "text": f"post {i}", "posted_at": "2026-09-20T00:00:00Z"} for i in range(start, start + count)]}


def test_from_api_reads_metrics_and_falls_back_to_created_at():
    post = Post.from_api({"id": 7, "text": "hi", "created_at": "2026-09-01T00:00:00Z", "metrics": {"likes": 3}})
    assert post.id == "7"
    assert post.posted_at == "2026-09-01T00:00:00Z"
    assert post.metrics == {"likes": 3}


def test_from_api_tolerates_missing_fields():
    post = Post.from_api({})
    assert post.text == ""
    assert post.metrics == {}


def test_fetch_stops_on_short_page():
    calls = []

    def runner(args):
        calls.append(list(args))
        return _page(3)

    assert len(fetch_posts(runner=runner)) == 3
    assert len(calls) == 1
    assert "--page" in calls[0] and calls[0][calls[0].index("--page") + 1] == "1"


def test_fetch_paginates_until_short_page():
    pages = [_page(MAX_PAGE_SIZE), _page(MAX_PAGE_SIZE, start=100), _page(5, start=200)]

    def runner(args):
        return pages[int(args[args.index("--page") + 1]) - 1]

    assert len(fetch_posts(runner=runner)) == 2 * MAX_PAGE_SIZE + 5


def test_fetch_respects_limit_and_never_overfetches():
    requested = []

    def runner(args):
        size = int(args[args.index("--limit") + 1])
        requested.append(size)
        return _page(size)

    posts = fetch_posts(limit=150, runner=runner)
    assert len(posts) == 150
    assert requested == [MAX_PAGE_SIZE, 50]


def test_fetch_passes_date_range():
    seen = []

    def runner(args):
        seen.extend(args)
        return _page(1)

    fetch_posts(since="2026-09-01T00:00:00Z", until="2026-09-30T00:00:00Z", runner=runner)
    assert "--since" in seen and "2026-09-01T00:00:00Z" in seen
    assert "--until" in seen and "2026-09-30T00:00:00Z" in seen


@pytest.mark.parametrize("payload", [[], {"items": []}])
def test_fetch_rejects_unexpected_payloads(payload):
    with pytest.raises(SuperXError):
        fetch_posts(runner=lambda args: payload)
