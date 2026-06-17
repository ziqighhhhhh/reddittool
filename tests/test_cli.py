from typer.testing import CliRunner

from reddit_pain_search.cli import app
from reddit_pain_search.config import load_config
from reddit_pain_search.models import (
    AnalysisStatus,
    ClassificationResult,
    ContentItem,
    PainCategory,
    SourceType,
)
import threading


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


def make_other_content() -> ContentItem:
    return ContentItem(
        source_type=SourceType.POST,
        reddit_id="old-post",
        product_name="Notion",
        subreddit="SaaS",
        title="Old Notion issue",
        text="Old uncached item",
        score=1,
        url="https://reddit.com/old-post",
        created_utc=1_600_000_000.0,
    )


class FakeRedditClient:
    def __init__(self):
        self.exclude_reddit_ids = None
        self.max_search_scrolls = None
        self.search_product_calls = 0

    def search_product(
        self,
        product_name,
        *,
        limit_posts,
        comments_per_post,
        exclude_reddit_ids=frozenset(),
        max_search_scrolls=None,
    ):
        self.search_product_calls += 1
        assert product_name == "Notion"
        assert limit_posts == 1
        assert comments_per_post == 0
        self.exclude_reddit_ids = set(exclude_reddit_ids)
        self.max_search_scrolls = max_search_scrolls
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


class FailingClassifier:
    def classify(self, item):
        raise RuntimeError("invalid authentication")


class ModelCapturingClassifier:
    def __init__(self):
        self.model_name = None
        self.calls = 0

    def set_model(self, model: str) -> None:
        self.model_name = model

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
    reddit_client = FakeRedditClient()

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
        obj={"reddit_client": reddit_client, "classifier": classifier},
    )

    assert result.exit_code == 0
    assert out.exists()
    assert "Wrote 1 rows" in result.stdout
    assert classifier.calls == 1
    assert reddit_client.exclude_reddit_ids == set()
    assert reddit_client.max_search_scrolls is None


def test_cli_allows_explicit_search_scroll_override(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    reddit_client = FakeRedditClient()

    result = runner.invoke(
        app,
        [
            "Notion",
            "--limit-posts",
            "1",
            "--comments-per-post",
            "0",
            "--search-scrolls",
            "12",
            "--out",
            str(out),
            "--database",
            str(db),
        ],
        obj={"reddit_client": reddit_client, "classifier": FakeClassifier()},
    )

    assert result.exit_code == 0
    assert reddit_client.max_search_scrolls == 12


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


def test_cli_reports_classifier_failure(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"

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
        obj={"reddit_client": FakeRedditClient(), "classifier": FailingClassifier()},
    )

    assert result.exit_code == 1
    assert "LLM classification failed" in result.stderr
    assert "LLM_API_KEY" in result.stderr


def test_cli_classifies_all_unanalyzed_cached_items_and_excludes_known_reddit_ids(tmp_path):
    from reddit_pain_search.repository import Repository

    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    Repository(db).save_content_items([make_other_content()])
    classifier = FakeClassifier()
    reddit_client = FakeRedditClient()

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
        obj={"reddit_client": reddit_client, "classifier": classifier},
    )

    assert result.exit_code == 0
    assert classifier.calls == 2
    assert reddit_client.exclude_reddit_ids == {"old-post"}
    assert "Classifying 2 uncached items" in result.stdout


def test_cli_model_override_is_passed_to_classifier(tmp_path, monkeypatch):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"

    from reddit_pain_search.classifier import KimiClassifier

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    config = load_config()

    real_classifier = KimiClassifier.from_config(config)
    classifier = ModelCapturingClassifier()
    reddit_client = FakeRedditClient()

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
            "--llm-model",
            "glm-5.1",
        ],
        obj={"reddit_client": reddit_client, "classifier": real_classifier, "model_callback": classifier.set_model},
    )

    assert result.exit_code == 0
    assert classifier.model_name == "glm-5.1"


def test_cli_classifies_concurrently(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"

    class ConcurrentTrackingClassifier:
        def __init__(self):
            self.calls = 0
            self.max_concurrent = 0
            self.active = 0

        def classify(self, item):
            self.active += 1
            self.calls += 1
            self.max_concurrent = max(self.max_concurrent, self.active)
            import time

            time.sleep(0.05)
            self.active -= 1
            return ClassificationResult(
                content_hash=item.content_hash,
                is_pain_point=True,
                category=PainCategory.USABILITY,
                confidence=0.9,
                reason="Hard to use",
                analysis_status=AnalysisStatus.SUCCESS,
                error_message=None,
            )

    classifier = ConcurrentTrackingClassifier()
    reddit_client = FakeRedditClient()

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
        obj={"reddit_client": reddit_client, "classifier": classifier},
    )

    assert result.exit_code == 0
    assert classifier.calls == 1


def test_cli_stops_on_first_classification_failure(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"

    class FailingClassifier:
        def __init__(self):
            self.calls = 0

        def classify(self, item):
            self.calls += 1
            raise RuntimeError("boom")

    classifier = FailingClassifier()
    reddit_client = FakeRedditClient()

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
        obj={"reddit_client": reddit_client, "classifier": classifier},
    )

    assert result.exit_code == 1
    assert "LLM classification failed" in result.stderr
    assert classifier.calls == 1


def test_cli_preserves_analysis_saved_before_failure(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    from reddit_pain_search.repository import Repository

    repo = Repository(db)
    repo.save_content_items([make_other_content()])

    class ImmediateFailingClassifier:
        def __init__(self):
            self.calls = 0

        def classify(self, item):
            self.calls += 1
            if item.reddit_id == "post1":
                raise RuntimeError("boom")
            return ClassificationResult(
                content_hash=item.content_hash,
                is_pain_point=True,
                category=PainCategory.USABILITY,
                confidence=0.9,
                reason="Hard to use",
                analysis_status=AnalysisStatus.SUCCESS,
                error_message=None,
            )

    classifier = ImmediateFailingClassifier()
    reddit_client = FakeRedditClient()

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
        obj={"reddit_client": reddit_client, "classifier": classifier},
    )

    assert result.exit_code == 1
    assert "LLM classification failed" in result.stderr
    assert repo.get_analysis(make_other_content().content_hash) is None


def test_cli_analyze_only_skips_fetch_and_classifies_unanalyzed_items(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    from reddit_pain_search.repository import Repository

    repo = Repository(db)
    repo.save_content_items([make_other_content(), make_content()])
    classifier = FakeClassifier()
    reddit_client = FakeRedditClient()

    result = runner.invoke(
        app,
        [
            "_all_",
            "--analyze-only",
            "--out",
            str(out),
            "--database",
            str(db),
        ],
        obj={"reddit_client": reddit_client, "classifier": classifier},
    )

    assert result.exit_code == 0
    assert classifier.calls == 2
    assert reddit_client.search_product_calls == 0
    assert "Classifying 2 uncached items across all products" in result.stdout
    assert "Fetched" not in result.stdout
    assert (tmp_path / "report-Notion.csv").exists()


def test_cli_analyze_only_with_no_unanalyzed_items(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    from reddit_pain_search.repository import Repository

    repo = Repository(db)
    repo.save_content_items([make_other_content()])
    repo.save_analysis(
        ClassificationResult(
            content_hash=make_other_content().content_hash,
            is_pain_point=True,
            category=PainCategory.USABILITY,
            confidence=0.9,
            reason="ok",
            analysis_status=AnalysisStatus.SUCCESS,
            error_message=None,
        )
    )
    classifier = FakeClassifier()
    reddit_client = FakeRedditClient()

    result = runner.invoke(
        app,
        [
            "_all_",
            "--analyze-only",
            "--out",
            str(out),
            "--database",
            str(db),
        ],
        obj={"reddit_client": reddit_client, "classifier": classifier},
    )

    assert result.exit_code == 0
    assert classifier.calls == 0
    assert reddit_client.search_product_calls == 0
    assert "No unanalyzed items found" in result.stdout


def test_cli_analyze_only_supports_model_override(tmp_path, monkeypatch):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    from reddit_pain_search.repository import Repository
    from reddit_pain_search.classifier import KimiClassifier

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    repo = Repository(db)
    repo.save_content_items([make_content()])

    real_classifier = KimiClassifier.from_config(load_config())
    classifier = ModelCapturingClassifier()
    reddit_client = FakeRedditClient()

    result = runner.invoke(
        app,
        [
            "_all_",
            "--analyze-only",
            "--llm-model",
            "glm-5.1",
            "--out",
            str(out),
            "--database",
            str(db),
        ],
        obj={"reddit_client": reddit_client, "classifier": real_classifier, "model_callback": classifier.set_model},
    )

    assert result.exit_code == 0
    assert classifier.model_name == "glm-5.1"


def test_cli_analyze_only_exports_one_csv_per_product(tmp_path):
    out = tmp_path / "report.csv"
    db = tmp_path / "cache.sqlite3"
    from reddit_pain_search.repository import Repository

    repo = Repository(db)
    notion_item = ContentItem(
        source_type=SourceType.POST,
        reddit_id="notion1",
        product_name="Notion",
        subreddit="SaaS",
        title="Notion issue",
        text="Notion is hard to use",
        score=10,
        url="https://reddit.com/notion1",
        created_utc=1_700_000_000.0,
    )
    figma_item = ContentItem(
        source_type=SourceType.POST,
        reddit_id="figma1",
        product_name="Figma",
        subreddit="design",
        title="Figma issue",
        text="Figma is slow",
        score=5,
        url="https://reddit.com/figma1",
        created_utc=1_700_000_000.0,
    )
    repo.save_content_items([notion_item, figma_item])

    classifier = FakeClassifier()
    reddit_client = FakeRedditClient()

    result = runner.invoke(
        app,
        [
            "_all_",
            "--analyze-only",
            "--out",
            str(out),
            "--database",
            str(db),
        ],
        obj={"reddit_client": reddit_client, "classifier": classifier},
    )

    assert result.exit_code == 0
    assert classifier.calls == 2
    assert (tmp_path / "report-Notion.csv").exists()
    assert (tmp_path / "report-Figma.csv").exists()
    assert "Wrote 1 rows" in result.stdout
