from reddit_pain_search.models import (
    AnalysisStatus,
    ClassificationResult,
    ContentItem,
    PainCategory,
    SourceType,
)
from reddit_pain_search.repository import Repository


def make_content(reddit_id: str, score: int = 10, text: str = "This is hard to use") -> ContentItem:
    return ContentItem(
        source_type=SourceType.POST,
        reddit_id=reddit_id,
        product_name="Notion",
        subreddit="SaaS",
        title="Notion issue",
        text=text,
        score=score,
        url=f"https://reddit.com/{reddit_id}",
        created_utc=1_700_000_000.0,
    )


def make_analysis(content_hash: str, is_pain_point: bool = True) -> ClassificationResult:
    return ClassificationResult(
        content_hash=content_hash,
        is_pain_point=is_pain_point,
        category=PainCategory.USABILITY if is_pain_point else PainCategory.NONE,
        confidence=0.9 if is_pain_point else 0.0,
        reason="Hard to use" if is_pain_point else "",
        analysis_status=AnalysisStatus.SUCCESS,
        error_message=None,
    )


def test_repository_saves_and_deduplicates_content(tmp_path):
    repo = Repository(tmp_path / "test.sqlite3")
    item = make_content("abc")

    repo.save_content_items([item])
    repo.save_content_items([item])

    rows = repo.list_content_for_product("Notion")
    assert rows == [item]


def test_repository_finds_unanalyzed_items(tmp_path):
    repo = Repository(tmp_path / "test.sqlite3")
    first = make_content("abc", text="Hard to use")
    second = make_content("def", text="Easy to use")
    repo.save_content_items([first, second])
    repo.save_analysis(make_analysis(first.content_hash))

    unanalyzed = repo.list_unanalyzed_content("Notion")

    assert unanalyzed == [second]


def test_repository_finds_all_unanalyzed_items(tmp_path):
    repo = Repository(tmp_path / "test.sqlite3")
    notion_analyzed = make_content("abc", text="Hard to use")
    notion_unanalyzed = make_content("def", text="Easy to use")
    figma_unanalyzed = ContentItem(
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
    repo.save_content_items([notion_analyzed, notion_unanalyzed, figma_unanalyzed])
    repo.save_analysis(make_analysis(notion_analyzed.content_hash))

    unanalyzed = repo.list_all_unanalyzed_content()

    assert unanalyzed == [figma_unanalyzed, notion_unanalyzed]


def test_repository_builds_report_rows_sorted(tmp_path):
    repo = Repository(tmp_path / "test.sqlite3")
    low_pain = make_content("low", score=1, text="Hard to use")
    high_non_pain = make_content("high", score=100, text="I like it")
    repo.save_content_items([high_non_pain, low_pain])
    repo.save_analysis(make_analysis(low_pain.content_hash, is_pain_point=True))
    repo.save_analysis(make_analysis(high_non_pain.content_hash, is_pain_point=False))

    rows = repo.list_report_rows("Notion")

    assert [row.content.reddit_id for row in rows] == ["low", "high"]
