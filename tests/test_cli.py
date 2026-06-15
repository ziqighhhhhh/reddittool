from typer.testing import CliRunner

from reddit_pain_search.cli import app
from reddit_pain_search.models import (
    AnalysisStatus,
    ClassificationResult,
    ContentItem,
    PainCategory,
    SourceType,
)


runner = CliRunner()


def make_content() -> ContentItem:
    return ContentItem(
        source_type=SourceType.POST,
        reddit_id="post1",
        product_name="Notion",
        subreddit="SaaS",
        title="Notion issue",
        text="Notion is hard to use",
        score=10,
        url="https://reddit.com/post1",
        created_utc=1_700_000_000.0,
    )


class FakeRedditClient:
    def search_product(self, product_name, *, limit_posts, comments_per_post):
        assert product_name == "Notion"
        assert limit_posts == 1
        assert comments_per_post == 0
        return [make_content()]


class FakeClassifier:
    def __init__(self):
        self.calls = 0

    def classify(self, item):
        self.calls += 1
        return ClassificationResult(
            content_hash=item.content_hash,
            is_pain_point=True,
            category=PainCategory.USABILITY,
            confidence=0.9,
            reason="Hard to use",
            analysis_status=AnalysisStatus.SUCCESS,
            error_message=None,
        )


def test_cli_generates_csv_with_injected_dependencies(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    classifier = FakeClassifier()

    result = runner.invoke(
        app,
        [
            "Notion",
            "--limit-posts",
            "1",
            "--comments-per-post",
            "0",
            "--out",
            str(out),
            "--database",
            str(db),
        ],
        obj={"reddit_client": FakeRedditClient(), "classifier": classifier},
    )

    assert result.exit_code == 0
    assert out.exists()
    assert "Wrote 1 rows" in result.stdout
    assert classifier.calls == 1


def test_cli_reuses_cached_analysis(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    classifier = FakeClassifier()
    args = [
        "Notion",
        "--limit-posts",
        "1",
        "--comments-per-post",
        "0",
        "--out",
        str(out),
        "--database",
        str(db),
    ]

    first = runner.invoke(app, args, obj={"reddit_client": FakeRedditClient(), "classifier": classifier})
    second = runner.invoke(app, args, obj={"reddit_client": FakeRedditClient(), "classifier": classifier})

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert classifier.calls == 1
