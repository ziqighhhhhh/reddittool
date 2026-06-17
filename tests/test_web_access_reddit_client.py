import pytest

from reddit_pain_search.models import SourceType
from reddit_pain_search.web_access_reddit_client import (
    BrowserProxyError,
    WebAccessRedditClient,
    _payload_to_items,
    _post_extraction_script,
)


class FakeBrowserProxy:
    def __init__(self):
        self.opened_urls = []
        self.closed_targets = []

    def open(self, url):
        self.opened_urls.append(url)
        return f"target-{len(self.opened_urls)}"

    def eval_json(self, target_id, script):
        if target_id == "target-1":
            return [
                {
                    "url": "https://www.reddit.com/r/SaaS/comments/post1/notion_problem/",
                    "title": "Notion problem",
                },
                {
                    "url": "https://www.reddit.com/r/SaaS/comments/post1/notion_problem/",
                    "title": "Duplicate Notion problem",
                },
            ]
        return {
            "reddit_id": "post1",
            "subreddit": "SaaS",
            "title": "Notion problem",
            "text": "Notion is difficult at scale",
            "score": 42,
            "url": "https://www.reddit.com/r/SaaS/comments/post1/notion_problem/",
            "created_utc": 1_700_000_000.0,
            "comments": [
                {
                    "reddit_id": "comment1",
                    "text": "I cannot organize this product",
                    "score": 12,
                    "url": "https://www.reddit.com/r/SaaS/comments/post1/notion_problem/comment/comment1/",
                    "created_utc": 1_700_000_001.0,
                },
                {
                    "reddit_id": "empty",
                    "text": "   ",
                    "score": 1,
                    "url": "https://www.reddit.com/r/SaaS/comments/post1/notion_problem/comment/empty/",
                    "created_utc": 1_700_000_002.0,
                },
            ],
        }

    def close(self, target_id):
        self.closed_targets.append(target_id)


class ProgressiveSearchProxy:
    def __init__(self):
        self.opened_urls = []
        self.closed_targets = []
        self.search_reads = 0
        self.scrolls = 0

    def open(self, url):
        self.opened_urls.append(url)
        return f"target-{len(self.opened_urls)}"

    def eval_json(self, target_id, script):
        if "window.scrollTo" in script:
            self.scrolls += 1
            return {"scrolled": True}
        if target_id == "target-1":
            self.search_reads += 1
            rows = [
                {
                    "url": "https://www.reddit.com/r/SaaS/comments/post1/notion_problem/",
                    "title": "Notion problem",
                },
            ]
            if self.scrolls:
                return [
                    *rows,
                    {
                        "url": "https://www.reddit.com/r/SaaS/comments/post2/more_notion_problem/",
                        "title": "More Notion problem",
                    },
                ]
            return rows
        post_id = f"post{len(self.opened_urls) - 1}"
        return {
            "reddit_id": post_id,
            "subreddit": "SaaS",
            "title": f"Notion problem {post_id}",
            "text": "Notion is difficult at scale",
            "score": 42,
            "url": f"https://www.reddit.com/r/SaaS/comments/{post_id}/notion_problem/",
            "created_utc": 1_700_000_000.0,
            "comments": [],
        }

    def close(self, target_id):
        self.closed_targets.append(target_id)


class FailingBrowserProxy:
    def open(self, url):
        raise BrowserProxyError("web-access CDP Proxy is not available")


def test_search_product_reads_reddit_pages_through_web_access():
    proxy = FakeBrowserProxy()
    client = WebAccessRedditClient(proxy)

    items = client.search_product("Notion", limit_posts=2, comments_per_post=1)

    assert "q=Notion" in proxy.opened_urls[0]
    assert len(proxy.opened_urls) == 2
    assert proxy.closed_targets == ["target-2", "target-1"]
    assert [item.source_type for item in items] == [SourceType.POST, SourceType.COMMENT]
    assert items[0].reddit_id == "post1"
    assert items[0].subreddit == "SaaS"
    assert items[0].score == 42
    assert items[1].reddit_id == "comment1"
    assert items[1].title == "Notion problem"


def test_search_product_scrolls_search_page_until_requested_post_count_is_loaded():
    proxy = ProgressiveSearchProxy()
    client = WebAccessRedditClient(proxy, sleep=lambda _: None)

    items = client.search_product(
        "Notion",
        limit_posts=2,
        comments_per_post=0,
        max_search_scrolls=3,
    )

    assert proxy.search_reads == 2
    assert proxy.scrolls == 1
    assert len(proxy.opened_urls) == 3
    assert [item.reddit_id for item in items] == ["post1", "post2"]


def test_search_product_automatically_estimates_scroll_limit_from_requested_posts():
    proxy = ProgressiveSearchProxy()
    client = WebAccessRedditClient(proxy, sleep=lambda _: None)

    items = client.search_product("Notion", limit_posts=2, comments_per_post=0)

    assert proxy.scrolls == 1
    assert [item.reddit_id for item in items] == ["post1", "post2"]


def test_search_product_validates_limits():
    client = WebAccessRedditClient(FakeBrowserProxy())

    with pytest.raises(ValueError, match="limit_posts must be at least 1"):
        client.search_product("Notion", limit_posts=0, comments_per_post=1)

    with pytest.raises(ValueError, match="comments_per_post must be 0 or greater"):
        client.search_product("Notion", limit_posts=1, comments_per_post=-1)

    with pytest.raises(ValueError, match="max_search_scrolls must be 0 or greater"):
        client.search_product("Notion", limit_posts=1, comments_per_post=0, max_search_scrolls=-1)


def test_search_product_reports_missing_web_access_proxy():
    client = WebAccessRedditClient(FailingBrowserProxy())

    with pytest.raises(BrowserProxyError, match="web-access CDP Proxy"):
        client.search_product("Notion", limit_posts=1, comments_per_post=0)


def test_search_product_skips_already_fetched_posts():
    proxy = FakeBrowserProxy()
    client = WebAccessRedditClient(proxy)

    items = client.search_product(
        "Notion",
        limit_posts=2,
        comments_per_post=1,
        exclude_reddit_ids={"post1"},
    )

    assert items == []
    assert len(proxy.opened_urls) == 1
    assert proxy.closed_targets == ["target-1"]


def test_payload_to_items_parses_compact_score_text_from_reddit_page():
    payload = {
        "reddit_id": "post1",
        "subreddit": "SaaS",
        "title": "Notion problem",
        "text": "Notion is difficult at scale",
        "score": "1.2k upvotes",
        "url": "https://www.reddit.com/r/SaaS/comments/post1/notion_problem/",
        "created_utc": 1_700_000_000.0,
        "comments": [
            {
                "reddit_id": "comment1",
                "text": "I cannot organize this product",
                "score": "345 points",
                "url": "https://www.reddit.com/r/SaaS/comments/post1/notion_problem/comment/comment1/",
                "created_utc": 1_700_000_001.0,
            }
        ],
    }

    items = _payload_to_items("Notion", payload, comments_per_post=1)

    assert items[0].score == 1200
    assert items[1].score == 345


def test_post_extraction_script_reads_scores_instead_of_returning_zero_literals():
    script = _post_extraction_script(comments_per_post=3)

    assert "extractPostScore" in script
    assert "extractCommentScore" in script
    assert "score: extractPostScore()" in script
    assert "score: extractCommentScore(node)" in script
