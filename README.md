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

## Data Source

This tool uses the Reddit official API through PRAW. It does not scrape Reddit web pages.

## Output

CSV rows are sorted with pain points first, then by Reddit score descending.
SQLite caches raw Reddit items and Kimi classification results.

## Safety

Secrets are read from `.env` or environment variables. Do not commit `.env`.
CSV text fields are escaped to reduce spreadsheet formula injection risk.

## Tests

```bash
pytest
```
