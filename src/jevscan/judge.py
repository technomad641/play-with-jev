"""Judging whether a post is about TypeSafe AI's Jev, using Jev."""

from __future__ import annotations

import re
from dataclasses import dataclass

from typesafe_sdk import Choice, Noul, NoulCriteria, Score, TypeSafeClient

from jevscan.posts import Post

# A cheap, deliberately generous net. It only decides what is worth asking about;
# Jev decides what actually counts, so over-matching here is harmless.
CANDIDATE_PATTERN = re.compile(r"\bjev\w*|\btype[\s-]?safe\b|\bsystem[\s-]?one\b|\bsystemone\b", re.IGNORECASE)

ANGLES = ("launch_news", "technical", "building", "opinion", "unrelated")

QUESTIONS = {
    "about_jev": Noul(
        instructions=(
            "Does this X post discuss Jev, the System One decision model built by the AI lab TypeSafe AI, "
            "or TypeSafe AI itself?"
        ),
        criteria=NoulCriteria(
            true=(
                "The post refers to TypeSafe AI's Jev model, or to System One models generally: their typed "
                "answers and probabilities, using them for routing, classification or scoring, their speed or "
                "cost compared with ordinary language models, the TypeSafe API or SDKs, or TypeSafe AI as a company."
            ),
            false=(
                "'Jev' here is an unrelated name, such as a person, a handle, the rapper jev., or the gaming "
                "YouTuber Jev. Or the post is about type safety as a general programming idea, or about some "
                "other product that merely shares one of these words, with no connection to TypeSafe AI."
            ),
        ),
    ),
    "angle": Choice(
        instructions=(
            "Assuming this X post is about TypeSafe AI's Jev model, what is the post mainly doing with it?"
        ),
        criteria={
            "launch_news": "Reporting or reacting to news: the launch, the funding, availability, or waitlist access.",
            "technical": (
                "Explaining how it works or how it performs: single-pass rather than token-by-token generation, "
                "typed answers, probabilities or calibration, latency, cost, or benchmark numbers."
            ),
            "building": (
                "The author is using it: shipping a feature, sharing code or an integration, or showing a demo "
                "they built."
            ),
            "opinion": (
                "Arguing a position about it: what it means for AI products, praise, skepticism, hype, or a "
                "comparison against language models, without building or explaining the mechanism."
            ),
            "unrelated": "The post is not about TypeSafe AI's Jev at all.",
        },
    ),
    "depth": Score(
        instructions=(
            "Assuming this X post is about TypeSafe AI's Jev model, how much substance does it carry about it?"
        ),
        criteria=[
            "The name appears but the post says nothing about what it is or what it does.",
            "A short reaction with no specifics: excitement, a bare link, or a one-line take.",
            "A real point: it explains a capability, a use case, a limitation, or a number, or reports hands-on experience.",
            "A detailed account: working code, benchmark results, an architecture explanation, or a build write-up.",
        ],
    ),
}


@dataclass(frozen=True)
class Judgment:
    post: Post
    about_jev: float
    angle: str
    angle_confidence: float
    depth: float
    depth_confidence: float

    def is_match(self, threshold: float) -> bool:
        return self.about_jev >= threshold


def find_candidates(posts: list[Post]) -> list[Post]:
    """Keep only posts whose text could plausibly concern Jev."""
    return [post for post in posts if CANDIDATE_PATTERN.search(post.text)]


def judge_post(client: TypeSafeClient, post: Post, *, model: str | None = None) -> Judgment:
    """Ask all three questions about one post in a single request."""
    response = client.system_one(
        state={"post_text": post.text},
        questions=QUESTIONS,
        model=model,
    )
    angle = response.choices["angle"]
    depth = response.scores["depth"]
    return Judgment(
        post=post,
        about_jev=response.nouls["about_jev"].noul,
        angle=angle.choice,
        angle_confidence=angle.confidence,
        depth=depth.score,
        depth_confidence=depth.confidence,
    )
