import csv

from reddit_pain_search.exporter import escape_csv_text, export_csv
from reddit_pain_search.models import (
    AnalysisStatus,
    ClassificationResult,
    ContentItem,
    PainCategory,
    ReportRow,
    SourceType,
)


def make_row(text: str, score: int, is_pain_point: bool) -> ReportRow:
    content = ContentItem(
        source_type=SourceType.COMMENT,
        reddit_id=text,
        product_name="Notion",
        subreddit="SaaS",
        title="Title",
        text=text,
        score=score,
        url="https://reddit.com/item",
        created_utc=1_700_000_000.0,
    )
    analysis = ClassificationResult(
        content_hash=content.content_hash,
        is_pain_point=is_pain_point,
        category=PainCategory.USABILITY if is_pain_point else PainCategory.NONE,
        confidence=0.8 if is_pain_point else 0.0,
        reason="Pain" if is_pain_point else "",
        analysis_status=AnalysisStatus.SUCCESS,
        error_message=None,
    )
    return ReportRow(content=content, analysis=analysis)


def test_escape_csv_text_prefixes_formula_values():
    assert escape_csv_text("=cmd") == "'=cmd"
    assert escape_csv_text("+cmd") == "'+cmd"
    assert escape_csv_text("-cmd") == "'-cmd"
    assert escape_csv_text("@cmd") == "'@cmd"
    assert escape_csv_text("normal") == "normal"


def test_export_csv_writes_sorted_rows(tmp_path):
    out = tmp_path / "report.csv"
    rows = [
        make_row("not pain high", score=100, is_pain_point=False),
        make_row("pain low", score=1, is_pain_point=True),
    ]

    export_csv(rows, out)

    with out.open(newline="", encoding="utf-8") as handle:
        exported = list(csv.DictReader(handle))
    assert [row["text"] for row in exported] == ["pain low", "not pain high"]
    assert exported[0]["is_pain_point"] == "true"


def test_export_csv_escapes_text_fields(tmp_path):
    out = tmp_path / "report.csv"
    export_csv([make_row("=danger", score=1, is_pain_point=True)], out)

    with out.open(newline="", encoding="utf-8") as handle:
        exported = list(csv.DictReader(handle))
    assert exported[0]["text"] == "'=danger"
