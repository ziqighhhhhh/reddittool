from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    POST = "post"
    COMMENT = "comment"


class PainCategory(str, Enum):
    BUG = "bug"
    PRICING = "pricing"
    USABILITY = "usability"
    MISSING_FEATURE = "missing_feature"
    SUPPORT = "support"
    PERFORMANCE = "performance"
    PRIVACY_SECURITY = "privacy_security"
    OTHER = "other"
    NONE = "none"


class AnalysisStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ImmutableModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ContentItem(ImmutableModel):
    source_type: SourceType
    reddit_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1, max_length=120)
    subreddit: str = Field(min_length=1)
    title: str
    text: str
    score: int
    url: str = Field(min_length=1)
    created_utc: float

    @property
    def content_hash(self) -> str:
        return build_content_hash(self.product_name, self.text)


class ClassificationResult(ImmutableModel):
    content_hash: str = Field(min_length=1)
    is_pain_point: bool
    category: PainCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    analysis_status: AnalysisStatus
    error_message: str | None = None

    @classmethod
    def failed(cls, content_hash: str, error_message: str) -> "ClassificationResult":
        return cls(
            content_hash=content_hash,
            is_pain_point=False,
            category=PainCategory.NONE,
            confidence=0.0,
            reason="",
            analysis_status=AnalysisStatus.FAILED,
            error_message=error_message,
        )


class ReportRow(ImmutableModel):
    content: ContentItem
    analysis: ClassificationResult | None


def validate_product_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Product name is required")
    if len(normalized) > 120:
        raise ValueError("Product name must be 120 characters or fewer")
    return normalized


def build_content_hash(product_name: str, text: str) -> str:
    normalized_product = product_name.strip().casefold()
    payload = f"{normalized_product}\n{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
