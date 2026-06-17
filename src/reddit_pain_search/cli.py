from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Annotated, Any

import typer

from reddit_pain_search.classifier import KimiClassifier
from reddit_pain_search.config import load_config
from reddit_pain_search.exporter import export_csv
from reddit_pain_search.models import validate_product_name
from reddit_pain_search.repository import Repository
from reddit_pain_search.web_access_reddit_client import WebAccessRedditClient


MAX_CLASSIFICATION_WORKERS = 10


app = typer.Typer(no_args_is_help=True)


@app.command()
def main(
    ctx: typer.Context,
    product_name: Annotated[str, typer.Argument()],
    limit_posts: Annotated[int, typer.Option("--limit-posts", min=1)] = 30,
    comments_per_post: Annotated[int, typer.Option("--comments-per-post", min=0)] = 10,
    search_scrolls: Annotated[int | None, typer.Option("--search-scrolls", min=0)] = None,
    out: Annotated[Path, typer.Option("--out")] = Path("results/reddit-pain-search.csv"),
    database: Annotated[Path | None, typer.Option("--database")] = None,
    llm_model: Annotated[str | None, typer.Option("--llm-model")] = None,
    analyze_only: Annotated[bool, typer.Option("--analyze-only")] = False,
) -> None:
    product = _validate_or_exit(product_name)
    config = None if _has_injected_dependencies(ctx) else load_config()
    database_path = database or Path(config.database_path if config else "reddit_pain_search.sqlite3")

    repository = Repository(database_path)
    classifier = _get_classifier(ctx, config, model_override=llm_model)

    if not analyze_only:
        reddit_client = _get_reddit_client(ctx, config)
        known_reddit_ids = {
            item.reddit_id
            for item in repository.list_content_for_product(product)
        }
        try:
            items = reddit_client.search_product(
                product,
                limit_posts=limit_posts,
                comments_per_post=comments_per_post,
                exclude_reddit_ids=known_reddit_ids,
                max_search_scrolls=search_scrolls,
            )
        except Exception as error:
            typer.echo(f"Reddit data fetch failed: {error}", err=True)
            raise typer.Exit(code=1) from error

        typer.echo(f"Fetched {len(items)} Reddit items.")
        repository.save_content_items(items)

    if analyze_only:
        unanalyzed_items = repository.list_all_unanalyzed_content()
        typer.echo(f"Classifying {len(unanalyzed_items)} uncached items across all products with up to {MAX_CLASSIFICATION_WORKERS} workers.")

        try:
            _classify_all(classifier, repository, unanalyzed_items)
        except Exception as error:
            typer.echo(
                "LLM classification failed. Check LLM_API_KEY, LLM_BASE_URL, "
                f"and LLM_MODEL in .env. Details: {error}",
                err=True,
            )
            raise typer.Exit(code=1) from error

        products = sorted({item.product_name for item in unanalyzed_items})
        if not products:
            typer.echo("No unanalyzed items found; nothing to export.")
            raise typer.Exit(code=0)

        output_directory = out if out.suffix == "" else out.parent
        output_name_stem = out.stem if out.suffix else "reddit-pain-search"
        for product in products:
            product_out = output_directory / f"{output_name_stem}-{product}.csv"
            rows = repository.list_report_rows(product)
            try:
                export_csv(rows, product_out)
            except OSError as error:
                typer.echo(f"CSV export failed: {error}", err=True)
                raise typer.Exit(code=1) from error
            typer.echo(f"Wrote {len(rows)} rows to {product_out}")
        return

    unanalyzed_items = repository.list_unanalyzed_content(product)
    typer.echo(f"Classifying {len(unanalyzed_items)} uncached items with up to {MAX_CLASSIFICATION_WORKERS} workers.")

    try:
        _classify_all(classifier, repository, unanalyzed_items)
    except Exception as error:
        typer.echo(
            "LLM classification failed. Check LLM_API_KEY, LLM_BASE_URL, "
            f"and LLM_MODEL in .env. Details: {error}",
            err=True,
        )
        raise typer.Exit(code=1) from error

    rows = repository.list_report_rows(product)
    try:
        export_csv(rows, out)
    except OSError as error:
        typer.echo(f"CSV export failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Wrote {len(rows)} rows to {out}")


def _classify_all(classifier, repository, items) -> None:
    if not items:
        return
    item_by_hash = {item.content_hash: item for item in items}
    completed_count = 0
    with ThreadPoolExecutor(max_workers=MAX_CLASSIFICATION_WORKERS) as executor:
        futures = {
            executor.submit(classifier.classify, item): item
            for item in items
        }
        try:
            for future in as_completed(futures):
                analysis = future.result()
                repository.save_analysis(analysis)
                completed_count += 1
                item = item_by_hash.get(analysis.content_hash)
                if item is None:
                    typer.echo(f"Warning: classified unknown content hash {analysis.content_hash}", err=True)
                    continue
                typer.echo(f"Classified {item.reddit_id}: pain_point={analysis.is_pain_point}, category={analysis.category.value}")
        except Exception:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise


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
    return WebAccessRedditClient.from_config(config, progress=typer.echo)


def _get_classifier(ctx: typer.Context, config: Any, model_override: str | None = None) -> Any:
    if ctx.obj and "classifier" in ctx.obj:
        classifier = ctx.obj["classifier"]
        if model_override and "model_callback" in ctx.obj:
            ctx.obj["model_callback"](model_override)
        return classifier
    resolved_config = config
    if model_override and resolved_config.llm_model != model_override:
        resolved_config = resolved_config.model_copy(update={"llm_model": model_override})
    return KimiClassifier.from_config(resolved_config)


if __name__ == "__main__":
    app()
