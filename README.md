# Reddit Pain Search

Personal CLI for finding product pain points in Reddit posts and comments.

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Fill `.env` with `MOONSHOT_API_KEY`.
For the default data source, Reddit API credentials are optional; the CLI reads
Reddit pages through the local `web-access` CDP Proxy.

Before running the CLI, start or verify the web-access proxy:

```bash
node C:\Users\1\.codex\skills\web-access\scripts\check-deps.mjs
```

The proxy should be available at `WEB_ACCESS_PROXY_URL`, which defaults to
`http://localhost:3456`.

## Usage

```bash
reddit-pain-search "Notion" --limit-posts 30 --comments-per-post 10 --out results/notion.csv
```

## Data Source

By default this tool uses `web-access` to open Reddit pages in the local Chrome
CDP session and extracts visible post/comment text for personal analysis. A
legacy PRAW adapter remains in the codebase, but the CLI no longer uses Reddit
Data API credentials for collection.

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
