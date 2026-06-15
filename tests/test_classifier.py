import json

from reddit_pain_search.classifier import KimiClassifier
from reddit_pain_search.models import AnalysisStatus, ContentItem, PainCategory, SourceType


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        assert kwargs["model"] == "kimi for coding"
        assert kwargs["response_format"] == {"type": "json_object"}
        return FakeResponse(self.content)


class FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = FakeChat(content)


def make_item() -> ContentItem:
    return ContentItem(
        source_type=SourceType.COMMENT,
        reddit_id="comment1",
        product_name="Notion",
        subreddit="SaaS",
        title="Notion problem",
        text="I cannot organize docs at scale.",
        score=10,
        url="https://reddit.com/item",
        created_utc=1_700_000_000.0,
    )


def test_classifier_parses_valid_json():
    content = json.dumps(
        {
            "is_pain_point": True,
            "category": "usability",
            "confidence": 0.84,
            "reason": "User cannot organize docs at scale.",
        }
    )
    client = FakeClient(content)
    classifier = KimiClassifier(client=client, model="kimi for coding")

    result = classifier.classify(make_item())

    assert result.is_pain_point is True
    assert result.category == PainCategory.USABILITY
    assert result.analysis_status == AnalysisStatus.SUCCESS


def test_classifier_returns_failed_result_after_invalid_json():
    client = FakeClient("not-json")
    classifier = KimiClassifier(client=client, model="kimi for coding")

    result = classifier.classify(make_item())

    assert result.is_pain_point is False
    assert result.category == PainCategory.NONE
    assert result.analysis_status == AnalysisStatus.FAILED
    assert "valid JSON" in result.error_message
    assert client.chat.completions.calls == 2
