# Reddit Pain Search Implementation Plan

> **For AI agents:** Required sub-skill: use `superpowers:executing-plans` to implement this plan task by task. Track progress by updating the checkboxes (`- [ ]`) in this file.

**Goal:** Build a personal Python CLI that searches Reddit through the official API, caches posts/comments in SQLite, classifies pain points with Kimi for Coding, and exports CSV reports.

**Architecture:** Use a small Python package with focused modules for configuration, models, persistence, Reddit API access, Kimi classification, CSV export, and CLI orchestration. The implementation is test-first and uses mocked external APIs for automated tests.

**Tech Stack:** Python 3.11+, Typer, Pydantic, PRAW, OpenAI-compatible client for Kimi/Moonshot, SQLite, pytest.

---

## File Structure

Create these files:

- `pyproject.toml`: package metadata, dependencies, console script, pytest configuration.
- `.gitignore`: ignore local environment, caches, build output, SQLite databases, and result files.
- `.env.example`: document required environment variables without secrets.
- `README.md`: local setup, Reddit/Kimi configuration, CLI examples, and test commands.
- `src/reddit_pain_search/__init__.py`: package marker and version export.
- `src/reddit_pain_search/models.py`: shared enums and immutable Pydantic models.
- `src/reddit_pain_search/config.py`: environment loading and validation.
- `src/reddit_pain_search/repository.py`: SQLite schema, persistence, cache lookups, and query result assembly.
- `src/reddit_pain_search/reddit_client.py`: Reddit official API adapter.
- `src/reddit_pain_search/classifier.py`: Kimi for Coding classifier and response validation.
- `src/reddit_pain_search/exporter.py`: CSV sorting and safe escaping.
- `src/reddit_pain_search/cli.py`: Typer CLI and workflow orchestration.
- `tests/test_models.py`: model validation and hash behavior.
- `tests/test_config.py`: config validation.
- `tests/test_repository.py`: SQLite persistence and cache behavior.
- `tests/test_exporter.py`: CSV output and formula injection escaping.
- `tests/test_classifier.py`: Kimi response parsing and failure behavior.
- `tests/test_cli.py`: CLI workflow with mocked dependencies.

Do not create a web UI, crawler, proxy integration, login automation, or real-credential test suite in this implementation.

---

### Task 1: Project Scaffold And Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `src/reddit_pain_search/__init__.py`

- [ ] **Step 1: Create packaging and dependency metadata**

Create `pyproject.toml` with this content:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "reddit-pain-search"
version = "0.1.0"
description = "Personal CLI for finding Reddit product pain points."
requires-python = ">=3.11"
dependencies = [
  "openai>=1.0.0",
  "praw>=7.7.0",
  "pydantic>=2.0.0",
  "python-dotenv>=1.0.0",
  "typer>=0.12.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0.0",
  "pytest-cov>=5.0.0",
]

[project.scripts]
reddit-pain-search = "reddit_pain_search.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=reddit_pain_search --cov-report=term-missing"
pythonpath = ["src"]
```

- [ ] **Step 2: Add local file hygiene**

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
*.db
*.sqlite
*.sqlite3
results/
dist/
build/
```

- [ ] **Step 3: Add example environment configuration**

Create `.env.example`:

```env
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=reddit-pain-search/0.1 by your_username
MOONSHOT_API_KEY=
KIMI_MODEL=kimi for coding
```

- [ ] **Step 4: Add setup README**

Create `README.md` with this content:

````markdown
# Reddit Pain Search

Personal CLI for finding product pain points in Reddit posts and comments.

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Fill `.env` with Reddit API credentials and `MOONSHOT_API_KEY`.

## Usage

```bash
reddit-pain-search "Notion" --limit-posts 30 --comments-per-post 10 --out results/notion.csv
```

## Tests

```bash
pytest
```
````

- [ ] **Step 5: Add package marker**

Create `src/reddit_pain_search/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 6: Run scaffold verification**

Run:

```bash
python -c "import reddit_pain_search; print(reddit_pain_search.__version__)"
```

Expected: prints `0.1.0`.

- [ ] **Step 7: Commit scaffold**

```bash
git add pyproject.toml .gitignore .env.example README.md src/reddit_pain_search/__init__.py
git commit -m "chore: scaffold python cli project"
```

---

### Task 2: Models And Validation

**Files:**
- Create: `src/reddit_pain_search/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
pytest tests/test_models.py -v
```

Expected: FAIL because `reddit_pain_search.models` does not exist.

- [ ] **Step 3: Implement immutable models**

Create `src/reddit_pain_search/models.py`:

```python
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
```

- [ ] **Step 4: Run model tests**

Run:

```bash
pytest tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit models**

```bash
git add src/reddit_pain_search/models.py tests/test_models.py
git commit -m "feat: add core data models"
```

---

### Task 3: Configuration Loading

**Files:**
- Create: `src/reddit_pain_search/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/test_config.py`:

```python
import pytest

from reddit_pain_search.config import AppConfig, load_config


def test_load_config_from_mapping():
    config = load_config(
        {
            "REDDIT_CLIENT_ID": "client",
            "REDDIT_CLIENT_SECRET": "secret",
            "REDDIT_USER_AGENT": "agent",
            "MOONSHOT_API_KEY": "moonshot",
            "KIMI_MODEL": "kimi for coding",
        }
    )

    assert config.reddit_client_id == "client"
    assert config.kimi_model == "kimi for coding"
    assert config.database_path == "reddit_pain_search.sqlite3"


def test_load_config_rejects_missing_secret():
    with pytest.raises(ValueError, match="MOONSHOT_API_KEY is required"):
        load_config(
            {
                "REDDIT_CLIENT_ID": "client",
                "REDDIT_CLIENT_SECRET": "secret",
                "REDDIT_USER_AGENT": "agent",
            }
        )


def test_config_repr_does_not_expose_secrets():
    config = AppConfig(
        reddit_client_id="client",
        reddit_client_secret="super-secret",
        reddit_user_agent="agent",
        moonshot_api_key="moonshot-secret",
        kimi_model="kimi for coding",
    )

    rendered = repr(config)
    assert "super-secret" not in rendered
    assert "moonshot-secret" not in rendered
```

- [ ] **Step 2: Run config tests and confirm failure**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: FAIL because `reddit_pain_search.config` does not exist.

- [ ] **Step 3: Implement config loading**

Create `src/reddit_pain_search/config.py`:

```python
from __future__ import annotations

import os
from collections.abc import Mapping

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class AppConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    reddit_client_id: str = Field(min_length=1)
    reddit_client_secret: SecretStr
    reddit_user_agent: str = Field(min_length=1)
    moonshot_api_key: SecretStr
    kimi_model: str = Field(default="kimi for coding", min_length=1)
    database_path: str = "reddit_pain_search.sqlite3"


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    if env is None:
        load_dotenv()
        env = os.environ

    return AppConfig(
        reddit_client_id=_required(env, "REDDIT_CLIENT_ID"),
        reddit_client_secret=_required(env, "REDDIT_CLIENT_SECRET"),
        reddit_user_agent=_required(env, "REDDIT_USER_AGENT"),
        moonshot_api_key=_required(env, "MOONSHOT_API_KEY"),
        kimi_model=env.get("KIMI_MODEL", "kimi for coding"),
        database_path=env.get("DATABASE_PATH", "reddit_pain_search.sqlite3"),
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value
```

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit config**

```bash
git add src/reddit_pain_search/config.py tests/test_config.py
git commit -m "feat: add environment configuration"
```

---

### Task 4: SQLite Repository

**Files:**
- Create: `src/reddit_pain_search/repository.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_repository.py`:

```python
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


def test_repository_builds_report_rows_sorted(tmp_path):
    repo = Repository(tmp_path / "test.sqlite3")
    low_pain = make_content("low", score=1, text="Hard to use")
    high_non_pain = make_content("high", score=100, text="I like it")
    repo.save_content_items([high_non_pain, low_pain])
    repo.save_analysis(make_analysis(low_pain.content_hash, is_pain_point=True))
    repo.save_analysis(make_analysis(high_non_pain.content_hash, is_pain_point=False))

    rows = repo.list_report_rows("Notion")

    assert [row.content.reddit_id for row in rows] == ["low", "high"]
```

- [ ] **Step 2: Run repository tests and confirm failure**

Run:

```bash
pytest tests/test_repository.py -v
```

Expected: FAIL because `reddit_pain_search.repository` does not exist.

- [ ] **Step 3: Implement SQLite schema and operations**

Create `src/reddit_pain_search/repository.py`:

```python
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
```

- [ ] **Step 4: Run repository tests**

Run:

```bash
pytest tests/test_repository.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit repository**

```bash
git add src/reddit_pain_search/repository.py tests/test_repository.py
git commit -m "feat: add sqlite cache repository"
```

---

### Task 5: CSV Exporter

**Files:**
- Create: `src/reddit_pain_search/exporter.py`
- Create: `tests/test_exporter.py`

- [ ] **Step 1: Write failing exporter tests**

Create `tests/test_exporter.py`:

```python
import csv

from reddit_pain_search.exporter import export_csv, escape_csv_text
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
```

- [ ] **Step 2: Run exporter tests and confirm failure**

Run:

```bash
pytest tests/test_exporter.py -v
```

Expected: FAIL because `reddit_pain_search.exporter` does not exist.

- [ ] **Step 3: Implement CSV exporter**

Create `src/reddit_pain_search/exporter.py`:

```python
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
```

- [ ] **Step 4: Run exporter tests**

Run:

```bash
pytest tests/test_exporter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit exporter**

```bash
git add src/reddit_pain_search/exporter.py tests/test_exporter.py
git commit -m "feat: add csv export"
```

---

### Task 6: Reddit API Adapter

**Files:**
- Create: `src/reddit_pain_search/reddit_client.py`
- Create or modify: `tests/test_reddit_client.py`

- [ ] **Step 1: Write failing Reddit adapter tests**

Create `tests/test_reddit_client.py`:

```python
from reddit_pain_search.models import SourceType
from reddit_pain_search.reddit_client import RedditClient


class FakeComment:
    id = "comment1"
    body = "I cannot organize this product"
    score = 12
    created_utc = 1_700_000_001.0
    permalink = "/r/SaaS/comments/post1/comment1"


class FakeCommentForest:
    def replace_more(self, limit):
        assert limit == 0

    def list(self):
        return [FakeComment()]


class FakeSubmission:
    id = "post1"
    title = "Notion problem"
    selftext = "Notion is difficult at scale"
    score = 50
    subreddit = "SaaS"
    permalink = "/r/SaaS/comments/post1/notion_problem"
    created_utc = 1_700_000_000.0
    comments = FakeCommentForest()


class FakeSubreddit:
    def search(self, query, limit, sort):
        assert query == "Notion"
        assert limit == 1
        assert sort == "relevance"
        return [FakeSubmission()]


class FakeReddit:
    def subreddit(self, name):
        assert name == "all"
        return FakeSubreddit()


def test_search_product_returns_post_and_comment_items():
    client = RedditClient(FakeReddit())

    items = client.search_product("Notion", limit_posts=1, comments_per_post=1)

    assert [item.source_type for item in items] == [SourceType.POST, SourceType.COMMENT]
    assert items[0].reddit_id == "post1"
    assert items[0].score == 50
    assert items[1].reddit_id == "comment1"
    assert items[1].title == "Notion problem"
```

- [ ] **Step 2: Run Reddit tests and confirm failure**

Run:

```bash
pytest tests/test_reddit_client.py -v
```

Expected: FAIL because `reddit_pain_search.reddit_client` does not exist.

- [ ] **Step 3: Implement Reddit adapter**

Create `src/reddit_pain_search/reddit_client.py`:

```python
from __future__ import annotations

from typing import Any

import praw

from reddit_pain_search.config import AppConfig
from reddit_pain_search.models import ContentItem, SourceType, validate_product_name


REDDIT_URL_PREFIX = "https://www.reddit.com"


class RedditClient:
    def __init__(self, reddit: Any) -> None:
        self._reddit = reddit

    @classmethod
    def from_config(cls, config: AppConfig) -> "RedditClient":
        reddit = praw.Reddit(
            client_id=config.reddit_client_id,
            client_secret=config.reddit_client_secret.get_secret_value(),
            user_agent=config.reddit_user_agent,
        )
        return cls(reddit)

    def search_product(
        self,
        product_name: str,
        *,
        limit_posts: int,
        comments_per_post: int,
    ) -> list[ContentItem]:
        product = validate_product_name(product_name)
        if limit_posts < 1:
            raise ValueError("limit_posts must be at least 1")
        if comments_per_post < 0:
            raise ValueError("comments_per_post must be 0 or greater")

        items: list[ContentItem] = []
        submissions = self._reddit.subreddit("all").search(product, limit=limit_posts, sort="relevance")
        for submission in submissions:
            post = _submission_to_content(submission, product)
            comments = _comments_to_content(submission, product, comments_per_post)
            items.extend([post, *comments])
        return items


def _submission_to_content(submission: Any, product_name: str) -> ContentItem:
    return ContentItem(
        source_type=SourceType.POST,
        reddit_id=str(submission.id),
        product_name=product_name,
        subreddit=str(submission.subreddit),
        title=str(submission.title or ""),
        text=str(submission.selftext or ""),
        score=int(submission.score),
        url=_full_url(str(submission.permalink)),
        created_utc=float(submission.created_utc),
    )


def _comments_to_content(submission: Any, product_name: str, comments_per_post: int) -> list[ContentItem]:
    if comments_per_post == 0:
        return []
    submission.comments.replace_more(limit=0)
    comments = sorted(
        submission.comments.list(),
        key=lambda comment: int(getattr(comment, "score", 0)),
        reverse=True,
    )[:comments_per_post]
    return [
        ContentItem(
            source_type=SourceType.COMMENT,
            reddit_id=str(comment.id),
            product_name=product_name,
            subreddit=str(submission.subreddit),
            title=str(submission.title or ""),
            text=str(getattr(comment, "body", "") or ""),
            score=int(getattr(comment, "score", 0)),
            url=_full_url(str(getattr(comment, "permalink", submission.permalink))),
            created_utc=float(getattr(comment, "created_utc", submission.created_utc)),
        )
        for comment in comments
        if str(getattr(comment, "body", "") or "").strip()
    ]


def _full_url(permalink: str) -> str:
    if permalink.startswith("http://") or permalink.startswith("https://"):
        return permalink
    return f"{REDDIT_URL_PREFIX}{permalink}"
```

- [ ] **Step 4: Run Reddit tests**

Run:

```bash
pytest tests/test_reddit_client.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Reddit adapter**

```bash
git add src/reddit_pain_search/reddit_client.py tests/test_reddit_client.py
git commit -m "feat: add reddit api adapter"
```

---

### Task 7: Kimi Classifier

**Files:**
- Create: `src/reddit_pain_search/classifier.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: Write failing classifier tests**

Create `tests/test_classifier.py`:

```python
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
```

- [ ] **Step 2: Run classifier tests and confirm failure**

Run:

```bash
pytest tests/test_classifier.py -v
```

Expected: FAIL because `reddit_pain_search.classifier` does not exist.

- [ ] **Step 3: Implement Kimi classifier**

Create `src/reddit_pain_search/classifier.py`:

```python
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from reddit_pain_search.config import AppConfig
from reddit_pain_search.models import AnalysisStatus, ClassificationResult, ContentItem, PainCategory


KIMI_BASE_URL = "https://api.moonshot.ai/v1"
MAX_TEXT_CHARS = 3000


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
            api_key=config.moonshot_api_key.get_secret_value(),
            base_url=KIMI_BASE_URL,
        )
        return cls(client=client, model=config.kimi_model)

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
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError, ValueError) as error:
                last_error = f"Kimi response was not valid JSON: {error}"
        return ClassificationResult.failed(item.content_hash, last_error)

    def _request_classification(self, item: ContentItem) -> KimiResponse:
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_prompt(item)},
            ],
        )
        content = response.choices[0].message.content
        payload = json.loads(content)
        return KimiResponse.model_validate(payload)


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
```

- [ ] **Step 4: Run classifier tests**

Run:

```bash
pytest tests/test_classifier.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit classifier**

```bash
git add src/reddit_pain_search/classifier.py tests/test_classifier.py
git commit -m "feat: add kimi pain classifier"
```

---

### Task 8: CLI Workflow

**Files:**
- Create: `src/reddit_pain_search/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run CLI tests and confirm failure**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL because `reddit_pain_search.cli` does not exist.

- [ ] **Step 3: Implement Typer CLI**

Create `src/reddit_pain_search/cli.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from reddit_pain_search.classifier import KimiClassifier
from reddit_pain_search.config import load_config
from reddit_pain_search.exporter import export_csv
from reddit_pain_search.models import validate_product_name
from reddit_pain_search.reddit_client import RedditClient
from reddit_pain_search.repository import Repository


app = typer.Typer(no_args_is_help=True)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    product_name: Annotated[str | None, typer.Argument()] = None,
    limit_posts: Annotated[int, typer.Option("--limit-posts", min=1)] = 30,
    comments_per_post: Annotated[int, typer.Option("--comments-per-post", min=0)] = 10,
    out: Annotated[Path, typer.Option("--out")] = Path("results/reddit-pain-search.csv"),
    database: Annotated[Path | None, typer.Option("--database")] = None,
) -> None:
    if product_name is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

    product = _validate_or_exit(product_name)
    config = None if _has_injected_dependencies(ctx) else load_config()
    database_path = database or Path(config.database_path if config else "reddit_pain_search.sqlite3")

    repository = Repository(database_path)
    reddit_client = _get_reddit_client(ctx, config)
    classifier = _get_classifier(ctx, config)

    try:
        items = reddit_client.search_product(
            product,
            limit_posts=limit_posts,
            comments_per_post=comments_per_post,
        )
    except Exception as error:
        typer.echo(f"Reddit API failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    repository.save_content_items(items)
    for item in repository.list_unanalyzed_content(product):
        analysis = classifier.classify(item)
        repository.save_analysis(analysis)

    rows = repository.list_report_rows(product)
    try:
        export_csv(rows, out)
    except OSError as error:
        typer.echo(f"CSV export failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Wrote {len(rows)} rows to {out}")


def _validate_or_exit(product_name: str) -> str:
    try:
        return validate_product_name(product_name)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error


def _has_injected_dependencies(ctx: typer.Context) -> bool:
    return bool(ctx.obj and "reddit_client" in ctx.obj and "classifier" in ctx.obj)


def _get_reddit_client(ctx: typer.Context, config: Any) -> Any:
    if ctx.obj and "reddit_client" in ctx.obj:
        return ctx.obj["reddit_client"]
    return RedditClient.from_config(config)


def _get_classifier(ctx: typer.Context, config: Any) -> Any:
    if ctx.obj and "classifier" in ctx.obj:
        return ctx.obj["classifier"]
    return KimiClassifier.from_config(config)
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit CLI**

```bash
git add src/reddit_pain_search/cli.py tests/test_cli.py
git commit -m "feat: add cli workflow"
```

---

### Task 9: Full Verification And Documentation Polish

**Files:**
- Modify: `README.md`
- Modify only if needed: source or tests from previous tasks.

- [ ] **Step 1: Run the full automated test suite**

Run:

```bash
pytest
```

Expected: PASS with coverage output. If coverage is below 80%, add focused tests for the lowest-covered module before continuing.

- [ ] **Step 2: Run package command help**

Run:

```bash
python -m pip install -e ".[dev]"
reddit-pain-search --help
```

Expected: command help renders and shows `product_name`, `--limit-posts`, `--comments-per-post`, `--out`, and `--database`.

- [ ] **Step 3: Update README with implemented behavior**

Ensure `README.md` includes:

```markdown
## Data Source

This tool uses the Reddit official API through PRAW. It does not scrape Reddit web pages.

## Output

CSV rows are sorted with pain points first, then by Reddit score descending.
SQLite caches raw Reddit items and Kimi classification results.

## Safety

Secrets are read from `.env` or environment variables. Do not commit `.env`.
CSV text fields are escaped to reduce spreadsheet formula injection risk.
```

- [ ] **Step 4: Commit verification polish**

```bash
git add README.md
git commit -m "docs: document usage and safety"
```

- [ ] **Step 5: Push all implementation commits**

Run:

```bash
git push origin main
```

Expected: all commits are pushed to `https://github.com/ziqighhhhhh/reddittool`.

---

## Manual Smoke Test

Run this only after `.env` has real credentials:

```bash
reddit-pain-search "Notion" --limit-posts 3 --comments-per-post 2 --out results/notion-smoke.csv
```

Expected:

- Command exits successfully.
- `results/notion-smoke.csv` exists.
- Rows include posts and comments.
- Rows include `score`, `url`, `is_pain_point`, `category`, `confidence`, and `reason`.
- A second run reuses cached classification for unchanged text.

Do not commit `.env`, SQLite databases, or files under `results/`.
