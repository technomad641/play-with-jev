import json

import httpx2
import pytest

from jevscan import cli
from jevscan.posts import Post, SuperXError

REAL_JEV = "Jev returns a typed decision in a single pass. 100x cheaper than an LLM for routing."
OTHER_JEV = "jev just dropped a new album and it is incredible"


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Wire the CLI to canned posts and a scripted Jev response per post."""

    def install(posts, verdicts):
        monkeypatch.setattr(cli, "fetch_posts", lambda **kwargs: posts)

        def handler(request: httpx2.Request) -> httpx2.Response:
            text = json.loads(request.content)["state"]["post_text"]
            noul, angle = verdicts[text]
            return httpx2.Response(
                200,
                json={
                    "model": "jev-1.13",
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                    "answers": {
                        "about_jev": {"type": "noul", "noul": noul},
                        "angle": {"type": "choice", "choice": angle, "confidence": 0.9, "probabilities": {angle: 0.9}},
                        "depth": {
                            "type": "score",
                            "score": 2.0,
                            "confidence": 0.8,
                            "legend": {"0": "a", "1": "b", "2": "c", "3": "d"},
                            "probabilities": {"2": 1.0},
                        },
                    },
                },
            )

        real_client = cli.TypeSafeClient
        monkeypatch.setattr(
            cli, "TypeSafeClient", lambda: real_client(api_key="test", transport=httpx2.MockTransport(handler))
        )

    return install


def test_disambiguates_the_two_meanings_of_jev(fake_pipeline, capsys):
    posts = [Post(id="1", text=REAL_JEV, url="https://x.com/u/status/1"), Post(id="2", text=OTHER_JEV)]
    fake_pipeline(posts, {REAL_JEV: (0.96, "technical"), OTHER_JEV: (0.02, "unrelated")})

    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "1 are about TypeSafe AI's Jev" in out
    assert "https://x.com/u/status/1" in out
    assert "Ruled out 1 post(s)" in out


def test_json_output_reports_every_judgment_with_its_verdict(fake_pipeline, capsys):
    posts = [Post(id="1", text=REAL_JEV), Post(id="2", text=OTHER_JEV)]
    fake_pipeline(posts, {REAL_JEV: (0.96, "technical"), OTHER_JEV: (0.02, "unrelated")})

    assert cli.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["scanned"] == 2
    assert payload["candidates"] == 2
    assert [j["is_match"] for j in payload["judgments"]] == [True, False]
    assert payload["judgments"][0]["post"]["text"] == REAL_JEV


def test_threshold_moves_the_cutoff(fake_pipeline, capsys):
    posts = [Post(id="1", text=REAL_JEV)]
    fake_pipeline(posts, {REAL_JEV: (0.6, "opinion")})

    assert cli.main(["--threshold", "0.9", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["judgments"][0]["is_match"] is False


def test_skips_the_api_entirely_when_nothing_mentions_jev(monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch_posts", lambda **kwargs: [Post(id="1", text="shipped a billing fix")])

    def explode():
        raise AssertionError("must not construct a client when there are no candidates")

    monkeypatch.setattr(cli, "TypeSafeClient", explode)

    assert cli.main([]) == 0
    assert "none mentioned Jev" in capsys.readouterr().out


def test_superx_failure_is_reported_as_an_error(monkeypatch, capsys):
    def fail(**kwargs):
        raise SuperXError("the `superx` CLI is not installed")

    monkeypatch.setattr(cli, "fetch_posts", fail)

    assert cli.main([]) == 1
    assert "error: the `superx` CLI is not installed" in capsys.readouterr().err


def test_missing_api_key_is_reported_as_an_error(monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch_posts", lambda **kwargs: [Post(id="1", text=REAL_JEV)])
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    assert cli.main([]) == 1
    assert "error:" in capsys.readouterr().err
