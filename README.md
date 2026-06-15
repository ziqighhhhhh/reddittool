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
