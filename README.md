# Reddit Pain Search

Personal CLI for finding product pain points in Reddit posts and comments.

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Fill `.env` with your Alibaba Cloud Bailian/DashScope API key and model config:

```env
LLM_API_KEY=your_dashscope_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.7-plus
```
For the default data source, Reddit API credentials are optional; the CLI reads
Reddit pages through the local `web-access` CDP Proxy.

Before running the CLI, start or verify the web-access proxy:

```bash
node C:\Users\1\.codex\skills\web-access\scripts\check-deps.mjs
```

The proxy should be available at `WEB_ACCESS_PROXY_URL`, which defaults to
`http://localhost:3456`.

## Usage

One-command run:

Double-click `run-agent.bat`, then enter the product name, post count, and
comments-per-post count when prompted. The scraper automatically estimates how
many times to scroll the Reddit search page from the requested post count.

Or run:

```cmd
run-agent.bat Notion 30 10
```

PowerShell:

```powershell
.\scripts\run-agent.ps1 "Notion"
```

With options:

```powershell
.\scripts\run-agent.ps1 "Notion" -LimitPosts 30 -CommentsPerPost 10 -Out results/notion.csv
```

The script verifies the `web-access` proxy before running the CLI.

Direct CLI usage:

```bash
reddit-pain-search "Notion" --limit-posts 30 --comments-per-post 10 --out results/notion.csv
```

Advanced override:

```bash
reddit-pain-search "Notion" --limit-posts 30 --comments-per-post 10 --search-scrolls 12 --out results/notion.csv
```

Switch LLM model per run (all use the same DashScope endpoint/key):

```bash
reddit-pain-search "Notion" --llm-model qwen3.7-max-2026-06-08
```

Available models include: `deepseek-v4-flash`, `qwen3.6-flash-2026-04-16`,
`qwen3.6-35b-a3b`, `qwen3.7-max-2026-05-17`, `qwen3.7-max-2026-06-08`,
`glm-5.1`, `qwen3.6-plus-2026-04-02`, `qwen3.7-max-preview`, `qwen3.6-plus`.
The default is `qwen3.7-plus`.

## Analyze-only mode

If you already have Reddit data in the SQLite cache and just want to run the LLM
classifier on items that have not yet been analyzed, use `--analyze-only`:

```bash
reddit-pain-search "_all_" --analyze-only
```

This skips Reddit fetching and classifies **all unanalyzed records across every
product** in the database. Results are exported as one CSV per product, for
example `results/reddit-pain-search-Notion.csv` and
`results/reddit-pain-search-Figma.csv`.

You can combine it with `--llm-model` to switch models:

```bash
reddit-pain-search "_all_" --analyze-only --llm-model glm-5.1
```

A Windows batch wrapper is included:

```cmd
analyze-only.bat
```

Or with a model override and custom output directory:

```cmd
analyze-only.bat "glm-5.1" "results"
```

The first argument is the LLM model (optional), the second is the output
folder (optional).

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
