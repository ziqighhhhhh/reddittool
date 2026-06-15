# Reddit Product Pain Search Design

## Context

Build a personal command-line tool that searches Reddit for product-related posts and comments, then classifies whether each item contains a user pain point. The first version prioritizes reliable collection, low operating complexity, and cost control through local caching.

This project starts from an empty workspace. There is no existing application structure or git history to preserve.

## Goals

- Accept a product name from the command line.
- Use the Reddit official API to search posts related to that product.
- Collect post title, body, score, subreddit, URL, and creation time.
- Collect the top comments for each post, including body, score, URL, parent post, and creation time.
- Classify each post and comment with Kimi for Coding to determine whether it contains a pain point.
- Export a CSV report sorted by pain-point status and Reddit score.
- Cache Reddit content and LLM analysis in SQLite to avoid duplicate work and duplicate API cost.

## Non-Goals

- Do not scrape Reddit web pages.
- Do not bypass Reddit limits.
- Do not simulate login or access private, deleted, or unavailable content.
- Do not build a web dashboard in the first version.
- Do not perform broad market analysis, trend forecasting, or competitor ranking.
- Do not train or fine-tune a model.

## User Interface

The first version is a Python CLI tool.

Example:

```bash
reddit-pain-search "Notion" --limit-posts 30 --comments-per-post 10 --out results/notion.csv
```

Primary options:

- `product_name`: required product name or keyword.
- `--limit-posts`: maximum number of Reddit posts to inspect.
- `--comments-per-post`: maximum number of top comments to inspect per post.
- `--out`: CSV output path.

Default behavior:

- Search Reddit for posts related to the product name.
- Fetch each post's top comments.
- Store raw Reddit content in SQLite.
- Analyze only items that do not already have cached analysis.
- Export current query results to CSV.
- Sort pain points first, then by `score` descending.

## Configuration

Secrets and runtime configuration come from environment variables or `.env`.

```env
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=
MOONSHOT_API_KEY=
KIMI_MODEL=kimi for coding
```

The first version only implements Kimi for Coding as the LLM classifier. `KIMI_MODEL` remains configurable so the exact provider model identifier can be adjusted without changing business logic if the API requires a different literal model id.

## Architecture

Use Python with small focused modules.

- `cli.py`: parse command arguments and orchestrate the workflow.
- `config.py`: load and validate environment configuration.
- `reddit_client.py`: call the Reddit official API.
- `repository.py`: manage SQLite persistence and deduplication.
- `classifier.py`: call Kimi for Coding and validate classification output.
- `exporter.py`: export CSV output safely.
- `models.py`: define shared data models.

Suggested dependencies:

- `praw` for Reddit API access.
- `openai` or the provider-compatible client for Moonshot/Kimi API calls.
- `pydantic` for configuration and response validation.
- `typer` for CLI ergonomics.
- `sqlite3` from the standard library, or SQLAlchemy only if repository complexity grows.
- `pytest` for automated tests.

## Data Flow

```text
product name
  -> CLI validation
  -> Reddit API post search
  -> post field extraction
  -> top comment extraction per post
  -> raw content SQLite cache
  -> Kimi classification for unanalyzed text
  -> schema validation
  -> analysis SQLite cache
  -> CSV export
```

## Data Model

Raw content fields:

- `source_type`: `post` or `comment`.
- `reddit_id`: stable Reddit item id.
- `product_name`: query product name.
- `subreddit`: subreddit name.
- `title`: post title or parent post title for comments.
- `text`: post body or comment body.
- `score`: Reddit score.
- `url`: Reddit URL.
- `created_utc`: Reddit creation timestamp.

Analysis fields:

- `content_hash`: SHA-256 hash based on normalized product name and text.
- `is_pain_point`: boolean.
- `category`: pain-point category.
- `confidence`: number from 0 to 1.
- `reason`: short explanation.
- `analysis_status`: `success`, `failed`, or `skipped`.
- `error_message`: nullable failure detail.

## Pain Point Classification

Each post or comment is classified independently. The classifier input includes:

- Product name.
- Source type.
- Title or parent post title.
- Text body.
- Reddit score.

The LLM must return structured JSON:

```json
{
  "is_pain_point": true,
  "category": "usability",
  "confidence": 0.86,
  "reason": "User complains that the product is hard to organize at scale."
}
```

Allowed categories:

- `bug`
- `pricing`
- `usability`
- `missing_feature`
- `support`
- `performance`
- `privacy_security`
- `other`
- `none`

Classification rules:

- Clear complaints, difficulties, unmet needs, migration reasons, or requests for alternatives count as pain points.
- Pure questions, tutorials, recommendations, promotions, and news do not count as pain points.
- Reddit `score` does not determine whether an item is a pain point; it is used only for sorting and prioritization.
- Very short or unclear text should be classified as `is_pain_point=false` and `category=none`.
- Invalid LLM output is retried once. If it is still invalid, mark the item as failed.

Cost controls:

- Cache classifications by `sha256(normalized_product_name + text)`.
- Do not reclassify cached text.
- Truncate very long text before sending it to the LLM.
- Prioritize higher-score content when limits are reached.

## SQLite Caching

Use SQLite as a local cache and result store.

Deduplication:

- Reddit content deduplicates by `reddit_id`.
- LLM analysis deduplicates by `content_hash`.

Expected behavior:

- Running the same query again should reuse cached content and analysis where possible.
- A new CSV can still be exported on every run.
- Failed analysis records should be visible and retryable in a later run.

## CSV Export

CSV columns:

- `source_type`
- `product_name`
- `subreddit`
- `title`
- `text`
- `score`
- `url`
- `created_utc`
- `is_pain_point`
- `category`
- `confidence`
- `reason`
- `analysis_status`
- `error_message`

Export rules:

- Pain points appear before non-pain points.
- Within each group, items sort by `score` descending.
- Text fields that begin with `=`, `+`, `-`, or `@` must be escaped to prevent CSV formula injection.

## Error Handling

- If Reddit API authentication or search fails, exit with a clear error and do not generate a misleading empty report.
- If comments fail for one post, keep the post, skip those comments, and record a warning.
- If Kimi API classification fails for one item, mark that item as `analysis_status=failed`.
- If Kimi returns invalid JSON or invalid fields, retry once, then record the error.
- If CSV export fails, exit with a clear path or permission error.

## Security

- Never hardcode API keys or secrets.
- Read secrets only from environment variables or `.env`.
- Do not log `REDDIT_CLIENT_SECRET` or `MOONSHOT_API_KEY`.
- Validate product name length and reject empty input.
- Use parameterized SQLite queries.
- Escape CSV formula prefixes in exported text fields.

## Testing Strategy

Unit tests:

- Product name validation.
- Environment configuration validation.
- LLM response schema validation.
- Pain-point category enum validation.
- CSV formula-injection escaping.
- Content hash generation.

Integration tests:

- Mock Reddit client returns posts and comments, then repository stores them.
- Mock Kimi client classifies unanalyzed text.
- Repeated runs do not call Kimi again for cached analysis.
- CSV output contains required fields and sorted rows.

CLI tests:

- Valid product name generates a CSV using mocked dependencies.
- Reddit API failure returns a non-zero exit code with a clear message.
- Kimi API item-level failure is recorded without aborting the whole run.

The first version should not require real Reddit or Kimi credentials in automated tests. Real API behavior is verified with a manual smoke test.

## Success Criteria

- A user can run one CLI command with a product name and receive a CSV report.
- The report includes Reddit posts and comments with score, URL, pain-point status, category, and reason.
- Repeating the same query reuses cached analysis instead of repeating Kimi calls.
- All automated tests pass.
- Secrets are not committed or logged.
