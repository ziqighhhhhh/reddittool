import pytest

from reddit_pain_search.config import AppConfig
from reddit_pain_search.models import SourceType
from reddit_pain_search.reddit_client import RedditClient


class FakeComment:
    id = "comment1"
    body = "I cannot organize this product"
    score = 12
    created_utc = 1_700_000_001.0
    permalink = "/r/SaaS/comments/post1/comment1"


class FakeCommentForest:
    def replace_more(self, limit):
        assert limit == 0

    def list(self):
        return [FakeComment()]


class FakeSubmission:
    id = "post1"
    title = "Notion problem"
    selftext = "Notion is difficult at scale"
    score = 50
    subreddit = "SaaS"
    permalink = "/r/SaaS/comments/post1/notion_problem"
    created_utc = 1_700_000_000.0
    comments = FakeCommentForest()


class FakeSubreddit:
    def search(self, query, limit, sort):
        assert query == "Notion"
        assert limit == 1
        assert sort == "relevance"
        return [FakeSubmission()]


class FakeReddit:
    def subreddit(self, name):
        assert name == "all"
        return FakeSubreddit()


def test_search_product_returns_post_and_comment_items():
    client = RedditClient(FakeReddit())

    items = client.search_product("Notion", limit_posts=1, comments_per_post=1)

    assert [item.source_type for item in items] == [SourceType.POST, SourceType.COMMENT]
    assert items[0].reddit_id == "post1"
    assert items[0].score == 50
    assert items[1].reddit_id == "comment1"
    assert items[1].title == "Notion problem"


def test_from_config_requires_reddit_api_credentials():
    config = AppConfig(moonshot_api_key="moonshot")

    with pytest.raises(ValueError, match="Reddit API credentials"):
        RedditClient.from_config(config)
