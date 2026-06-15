from __future__ import annotations

from typing import Any

import praw

from reddit_pain_search.config import AppConfig
from reddit_pain_search.models import ContentItem, SourceType, validate_product_name


REDDIT_URL_PREFIX = "https://www.reddit.com"


class RedditClient:
    def __init__(self, reddit: Any) -> None:
        self._reddit = reddit

    @classmethod
    def from_config(cls, config: AppConfig) -> "RedditClient":
        reddit = praw.Reddit(
            client_id=config.reddit_client_id,
            client_secret=config.reddit_client_secret.get_secret_value(),
            user_agent=config.reddit_user_agent,
        )
        return cls(reddit)

    def search_product(
        self,
        product_name: str,
        *,
        limit_posts: int,
        comments_per_post: int,
    ) -> list[ContentItem]:
        product = validate_product_name(product_name)
        if limit_posts < 1:
            raise ValueError("limit_posts must be at least 1")
        if comments_per_post < 0:
            raise ValueError("comments_per_post must be 0 or greater")

        items: list[ContentItem] = []
        submissions = self._reddit.subreddit("all").search(product, limit=limit_posts, sort="relevance")
        for submission in submissions:
            post = _submission_to_content(submission, product)
            comments = _comments_to_content(submission, product, comments_per_post)
            items.extend([post, *comments])
        return items


def _submission_to_content(submission: Any, product_name: str) -> ContentItem:
    return ContentItem(
        source_type=SourceType.POST,
        reddit_id=str(submission.id),
        product_name=product_name,
        subreddit=str(submission.subreddit),
        title=str(submission.title or ""),
        text=str(submission.selftext or ""),
        score=int(submission.score),
        url=_full_url(str(submission.permalink)),
        created_utc=float(submission.created_utc),
    )


def _comments_to_content(submission: Any, product_name: str, comments_per_post: int) -> list[ContentItem]:
    if comments_per_post == 0:
        return []
    submission.comments.replace_more(limit=0)
    comments = sorted(
        submission.comments.list(),
        key=lambda comment: int(getattr(comment, "score", 0)),
        reverse=True,
    )[:comments_per_post]
    return [
        ContentItem(
            source_type=SourceType.COMMENT,
            reddit_id=str(comment.id),
            product_name=product_name,
            subreddit=str(submission.subreddit),
            title=str(submission.title or ""),
            text=str(getattr(comment, "body", "") or ""),
            score=int(getattr(comment, "score", 0)),
            url=_full_url(str(getattr(comment, "permalink", submission.permalink))),
            created_utc=float(getattr(comment, "created_utc", submission.created_utc)),
        )
        for comment in comments
        if str(getattr(comment, "body", "") or "").strip()
    ]


def _full_url(permalink: str) -> str:
    if permalink.startswith("http://") or permalink.startswith("https://"):
        return permalink
    return f"{REDDIT_URL_PREFIX}{permalink}"
