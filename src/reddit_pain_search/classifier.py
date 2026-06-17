from __future__ import annotations

import json
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError
from pydantic import BaseModel, Field, ValidationError

from reddit_pain_search.config import AppConfig
from reddit_pain_search.models import AnalysisStatus, ClassificationResult, ContentItem, PainCategory


MAX_TEXT_CHARS = 3000
API_RETRY_ATTEMPTS = 2


class KimiResponse(BaseModel):
    is_pain_point: bool
    category: PainCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class KimiClassifier:
    def __init__(self, client: Any, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def from_config(cls, config: AppConfig) -> "KimiClassifier":
        client = OpenAI(
            api_key=config.llm_api_key.get_secret_value(),
            base_url=config.llm_base_url,
        )
        return cls(client=client, model=config.llm_model)

    def classify(self, item: ContentItem) -> ClassificationResult:
        last_error = "Kimi response was not valid JSON"
        for _ in range(2):
            try:
                parsed = self._request_classification(item)
                return ClassificationResult(
                    content_hash=item.content_hash,
                    is_pain_point=parsed.is_pain_point,
                    category=parsed.category,
                    confidence=parsed.confidence,
                    reason=parsed.reason,
                    analysis_status=AnalysisStatus.SUCCESS,
                    error_message=None,
                )
            except (APITimeoutError, APIConnectionError, RateLimitError, APIError):
                raise
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError) as error:
                last_error = f"Kimi response was not valid JSON: {error}"
        return ClassificationResult.failed(item.content_hash, last_error)

    def _request_classification(self, item: ContentItem) -> KimiResponse:
        last_api_error: Exception | None = None
        for attempt in range(API_RETRY_ATTEMPTS + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": _system_prompt()},
                        {"role": "user", "content": _user_prompt(item)},
                    ],
                )
            except APITimeoutError as error:
                last_api_error = error
                continue
            except APIConnectionError as error:
                last_api_error = error
                continue
            except RateLimitError as error:
                last_api_error = error
                continue
            except APIError as error:
                raise error
            content = response.choices[0].message.content
            payload = json.loads(content)
            return KimiResponse.model_validate(payload)
        raise last_api_error if last_api_error else RuntimeError("LLM API request failed")


def _system_prompt() -> str:
    return (
        "You classify Reddit posts and comments about a product. "
        "Return only JSON with is_pain_point, category, confidence, and reason. "
        "Pain points are clear complaints, difficulties, unmet needs, migration reasons, "
        "or requests for alternatives. Questions, tutorials, recommendations, promotions, "
        "and news are not pain points. Allowed categories: bug, pricing, usability, "
        "missing_feature, support, performance, privacy_security, other, none."
    )


def _user_prompt(item: ContentItem) -> str:
    text = item.text[:MAX_TEXT_CHARS]
    return (
        f"Product: {item.product_name}\n"
        f"Source type: {item.source_type.value}\n"
        f"Reddit score: {item.score}\n"
        f"Title: {item.title}\n"
        f"Text:\n{text}"
    )
