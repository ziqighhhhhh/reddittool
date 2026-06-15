from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from reddit_pain_search.models import AnalysisStatus, PainCategory, ReportRow


CSV_FIELDS = [
    "source_type",
    "product_name",
    "subreddit",
    "title",
    "text",
    "score",
    "url",
    "created_utc",
    "is_pain_point",
    "category",
    "confidence",
    "reason",
    "analysis_status",
    "error_message",
]


def export_csv(rows: Iterable[ReportRow], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            not bool(row.analysis and row.analysis.is_pain_point),
            -row.content.score,
            row.content.reddit_id,
        ),
    )

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(_row_to_dict(row) for row in sorted_rows)


def escape_csv_text(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _row_to_dict(row: ReportRow) -> dict[str, object]:
    analysis = row.analysis
    return {
        "source_type": row.content.source_type.value,
        "product_name": escape_csv_text(row.content.product_name),
        "subreddit": escape_csv_text(row.content.subreddit),
        "title": escape_csv_text(row.content.title),
        "text": escape_csv_text(row.content.text),
        "score": row.content.score,
        "url": row.content.url,
        "created_utc": row.content.created_utc,
        "is_pain_point": _bool_text(bool(analysis and analysis.is_pain_point)),
        "category": (analysis.category if analysis else PainCategory.NONE).value,
        "confidence": analysis.confidence if analysis else 0.0,
        "reason": escape_csv_text(analysis.reason if analysis else ""),
        "analysis_status": (analysis.analysis_status if analysis else AnalysisStatus.SKIPPED).value,
        "error_message": escape_csv_text(analysis.error_message if analysis and analysis.error_message else ""),
    }


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
