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


@app.command()
def main(
    ctx: typer.Context,
    product_name: Annotated[str, typer.Argument()],
    limit_posts: Annotated[int, typer.Option("--limit-posts", min=1)] = 30,
    comments_per_post: Annotated[int, typer.Option("--comments-per-post", min=0)] = 10,
    out: Annotated[Path, typer.Option("--out")] = Path("results/reddit-pain-search.csv"),
    database: Annotated[Path | None, typer.Option("--database")] = None,
) -> None:
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
