from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from reddit_pain_search.models import (
    AnalysisStatus,
    ClassificationResult,
    ContentItem,
    PainCategory,
    ReportRow,
    SourceType,
)


class Repository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._init_schema()

    def save_content_items(self, items: Iterable[ContentItem]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO content_items (
                    source_type, reddit_id, product_name, subreddit, title, text, score, url, created_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.source_type.value,
                        item.reddit_id,
                        item.product_name,
                        item.subreddit,
                        item.title,
                        item.text,
                        item.score,
                        item.url,
                        item.created_utc,
                    )
                    for item in items
                ],
            )

    def save_analysis(self, analysis: ClassificationResult) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO analysis_results (
                    content_hash, is_pain_point, category, confidence, reason, analysis_status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis.content_hash,
                    int(analysis.is_pain_point),
                    analysis.category.value,
                    analysis.confidence,
                    analysis.reason,
                    analysis.analysis_status.value,
                    analysis.error_message,
                ),
            )

    def list_content_for_product(self, product_name: str) -> list[ContentItem]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source_type, reddit_id, product_name, subreddit, title, text, score, url, created_utc
                FROM content_items
                WHERE lower(product_name) = lower(?)
                ORDER BY score DESC, reddit_id ASC
                """,
                (product_name,),
            ).fetchall()
        return [_content_from_row(row) for row in rows]

    def list_unanalyzed_content(self, product_name: str) -> list[ContentItem]:
        items = self.list_content_for_product(product_name)
        return [item for item in items if self.get_analysis(item.content_hash) is None]

    def get_analysis(self, content_hash: str) -> ClassificationResult | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT content_hash, is_pain_point, category, confidence, reason, analysis_status, error_message
                FROM analysis_results
                WHERE content_hash = ?
                """,
                (content_hash,),
            ).fetchone()
        return None if row is None else _analysis_from_row(row)

    def list_report_rows(self, product_name: str) -> list[ReportRow]:
        rows = [
            ReportRow(content=item, analysis=self.get_analysis(item.content_hash))
            for item in self.list_content_for_product(product_name)
        ]
        return sorted(
            rows,
            key=lambda row: (
                not bool(row.analysis and row.analysis.is_pain_point),
                -row.content.score,
                row.content.reddit_id,
            ),
        )

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS content_items (
                    reddit_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    subreddit TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    created_utc REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_results (
                    content_hash TEXT PRIMARY KEY,
                    is_pain_point INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    analysis_status TEXT NOT NULL,
                    error_message TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def _content_from_row(row: sqlite3.Row) -> ContentItem:
    return ContentItem(
        source_type=SourceType(row["source_type"]),
        reddit_id=row["reddit_id"],
        product_name=row["product_name"],
        subreddit=row["subreddit"],
        title=row["title"],
        text=row["text"],
        score=row["score"],
        url=row["url"],
        created_utc=row["created_utc"],
    )


def _analysis_from_row(row: sqlite3.Row) -> ClassificationResult:
    return ClassificationResult(
        content_hash=row["content_hash"],
        is_pain_point=bool(row["is_pain_point"]),
        category=PainCategory(row["category"]),
        confidence=row["confidence"],
        reason=row["reason"],
        analysis_status=AnalysisStatus(row["analysis_status"]),
        error_message=row["error_message"],
    )
