import json

import httpx2
import pytest
from typesafe_sdk import TypeSafeClient

from jevscan.judge import ANGLES, QUESTIONS, find_candidates, judge_post
from jevscan.posts import Post


def _answer_payload(*, noul=0.97, angle="technical", depth=2.4):
    return {
        "model": "jev-1.13",
        "usage": {"input_tokens": 120, "output_tokens": 3},
        "answers": {
            "about_jev": {"type": "noul", "noul": noul},
            "angle": {
                "type": "choice",
                "choice": angle,
                "confidence": 0.88,
                "probabilities": {name: (0.88 if name == angle else 0.03) for name in ANGLES},
            },
            "depth": {
                "type": "score",
                "score": depth,
                "confidence": 0.71,
                "legend": {str(i): text for i, text in enumerate(QUESTIONS["depth"].criteria)},
                "probabilities": {"0": 0.05, "1": 0.15, "2": 0.6, "3": 0.2},
            },
        },
    }


def _client(handler):
    return TypeSafeClient(api_key="test-key", transport=httpx2.MockTransport(handler))


def test_find_candidates_catches_the_relevant_spellings():
    texts = [
        "jev is fast",
        "Shipping with TypeSafe today",
        "System One models change routing",
        "type-safe code is good",  # over-matches on purpose; Jev rules it out
        "systemone ftw",
        "JevX extension is neat",
    ]
    posts = [Post(id=str(i), text=t) for i, t in enumerate(texts)]
    assert len(find_candidates(posts)) == len(texts)


def test_find_candidates_skips_unrelated_posts():
    posts = [Post(id="1", text="deployed the new billing service"), Post(id="2", text="coffee")]
    assert find_candidates(posts) == []


def test_judge_post_sends_expected_request_and_parses_answers():
    captured = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json=_answer_payload())

    post = Post(id="1", text="Jev returns typed decisions in one pass", url="https://x.com/u/status/1")
    with _client(handler) as client:
        judgment = judge_post(client, post)

    assert captured["url"] == "https://api.typesafe.ai/v1/systemone"
    assert captured["auth"] == "Bearer test-key"
    assert captured["body"]["model"] == "jev-latest"
    assert captured["body"]["state"] == {"post_text": post.text}
    assert set(captured["body"]["questions"]) == {"about_jev", "angle", "depth"}

    assert judgment.post is post
    assert judgment.about_jev == 0.97
    assert judgment.angle == "technical"
    assert judgment.angle_confidence == 0.88
    assert judgment.depth == 2.4
    assert judgment.depth_confidence == 0.71


def test_judge_post_honours_model_override():
    captured = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json=_answer_payload())

    with _client(handler) as client:
        judge_post(client, Post(id="1", text="jev"), model="jev-1.13")

    assert captured["body"]["model"] == "jev-1.13"


def test_question_payload_matches_the_documented_primitive_shapes():
    def handler(request: httpx2.Request) -> httpx2.Response:
        questions = json.loads(request.content)["questions"]
        assert questions["about_jev"]["type"] == "noul"
        assert set(questions["about_jev"]["criteria"]) == {"true", "false"}
        assert questions["angle"]["type"] == "choice"
        assert list(questions["angle"]["criteria"]) == list(ANGLES)
        assert questions["depth"]["type"] == "score"
        assert len(questions["depth"]["criteria"]) == 4
        return httpx2.Response(200, json=_answer_payload())

    with _client(handler) as client:
        judge_post(client, Post(id="1", text="jev"))


def test_unrelated_is_available_as_a_no_match_outcome():
    assert "unrelated" in ANGLES


@pytest.mark.parametrize("probability,threshold,expected", [(0.9, 0.5, True), (0.5, 0.5, True), (0.2, 0.5, False)])
def test_is_match_applies_threshold_inclusively(probability, threshold, expected):
    with _client(lambda request: httpx2.Response(200, json=_answer_payload(noul=probability))) as client:
        judgment = judge_post(client, Post(id="1", text="jev"))
    assert judgment.is_match(threshold) is expected
