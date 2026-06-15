import pytest
from pydantic import ValidationError

from reddit_pain_search.models import (
    AnalysisStatus,
    ClassificationResult,
    ContentItem,
    PainCategory,
    SourceType,
    build_content_hash,
    validate_product_name,
)


def test_validate_product_name_trims_input():
    assert validate_product_name("  Notion  ") == "Notion"


def test_validate_product_name_rejects_blank():
    with pytest.raises(ValueError, match="Product name is required"):
        validate_product_name("   ")


def test_validate_product_name_rejects_too_long():
    with pytest.raises(ValueError, match="Product name must be 120 characters or fewer"):
        validate_product_name("x" * 121)


def test_content_hash_normalizes_product_name():
    first = build_content_hash(" Notion ", "Same text")
    second = build_content_hash("notion", "Same text")
    assert first == second


def test_content_hash_changes_when_text_changes():
    first = build_content_hash("Notion", "First text")
    second = build_content_hash("Notion", "Second text")
    assert first != second


def test_content_item_requires_known_source_type():
    with pytest.raises(ValidationError):
        ContentItem(
            source_type="video",
            reddit_id="abc",
            product_name="Notion",
            subreddit="SaaS",
            title="Title",
            text="Body",
            score=10,
            url="https://reddit.com/r/SaaS/comments/abc",
            created_utc=1_700_000_000.0,
        )


def test_classification_result_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        ClassificationResult(
            content_hash="abc",
            is_pain_point=True,
            category=PainCategory.USABILITY,
            confidence=1.5,
            reason="Too high",
            analysis_status=AnalysisStatus.SUCCESS,
            error_message=None,
        )


def test_classification_result_supports_failed_status():
    result = ClassificationResult.failed("abc", "Kimi timeout")
    assert result.content_hash == "abc"
    assert result.is_pain_point is False
    assert result.category == PainCategory.NONE
    assert result.confidence == 0.0
    assert result.reason == ""
    assert result.analysis_status == AnalysisStatus.FAILED
    assert result.error_message == "Kimi timeout"


def test_enums_keep_expected_values():
    assert SourceType.POST.value == "post"
    assert SourceType.COMMENT.value == "comment"
    assert PainCategory.MISSING_FEATURE.value == "missing_feature"
