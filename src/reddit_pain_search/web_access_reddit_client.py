from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any
from urllib import error, parse, request

from reddit_pain_search.config import AppConfig
from reddit_pain_search.models import ContentItem, SourceType, validate_product_name


REDDIT_SEARCH_URL = "https://www.reddit.com/search/"
COMMENT_PATH_RE = re.compile(r"/r/(?P<subreddit>[^/]+)/comments/(?P<reddit_id>[^/]+)", re.IGNORECASE)
SCORE_TEXT_RE = re.compile(r"(?P<number>-?\d+(?:\.\d+)?)\s*(?P<suffix>[kKmM]?)")
MAX_AUTO_SEARCH_SCROLLS = 60
MIN_AUTO_SEARCH_SCROLLS = 3
POSTS_PER_SEARCH_SCROLL_ESTIMATE = 5
SEARCH_SCROLL_WAIT_SECONDS = 1.0


class BrowserProxyError(RuntimeError):
    pass


class BrowserProxy:
    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def open(self, url: str) -> str:
        payload = self._get_json(f"/new?url={parse.quote(url, safe='')}")
        target_id = _extract_target_id(payload)
        if not target_id:
            raise BrowserProxyError("web-access CDP Proxy did not return a target id")
        return target_id

    def eval_json(self, target_id: str, script: str) -> Any:
        raw_payload = self._post(f"/eval?target={parse.quote(target_id, safe='')}", script)
        payload = _unwrap_eval_payload(raw_payload)
        if isinstance(payload, str):
            return json.loads(payload)
        return payload

    def close(self, target_id: str) -> None:
        try:
            self._get_json(f"/close?target={parse.quote(target_id, safe='')}")
        except BrowserProxyError:
            return

    def _get_json(self, path: str) -> Any:
        return _decode_json(self._request("GET", path, None))

    def _post(self, path: str, body: str) -> Any:
        return _decode_json(self._request("POST", path, body.encode("utf-8")))

    def _request(self, method: str, path: str, body: bytes | None) -> bytes:
        url = f"{self._base_url}{path}"
        req = request.Request(url, data=body, method=method)
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as response:
                return response.read()
        except error.URLError as exc:
            raise BrowserProxyError(
                "web-access CDP Proxy is not available. Run "
                "`node C:\\Users\\1\\.codex\\skills\\web-access\\scripts\\check-deps.mjs` first."
            ) from exc


class WebAccessRedditClient:
    def __init__(
        self,
        proxy: BrowserProxy,
        progress: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._proxy = proxy
        self._progress = progress
        self._sleep = sleep

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        progress: Callable[[str], None] | None = None,
    ) -> "WebAccessRedditClient":
        return cls(BrowserProxy(config.web_access_proxy_url), progress=progress)

    def search_product(
        self,
        product_name: str,
        *,
        limit_posts: int,
        comments_per_post: int,
        exclude_reddit_ids: set[str] | frozenset[str] = frozenset(),
        max_search_scrolls: int | None = None,
    ) -> list[ContentItem]:
        product = validate_product_name(product_name)
        if limit_posts < 1:
            raise ValueError("limit_posts must be at least 1")
        if comments_per_post < 0:
            raise ValueError("comments_per_post must be 0 or greater")
        if max_search_scrolls is not None and max_search_scrolls < 0:
            raise ValueError("max_search_scrolls must be 0 or greater")
        search_scrolls = max_search_scrolls if max_search_scrolls is not None else _estimate_search_scrolls(limit_posts)

        self._report(f"Opening Reddit search for {product}...")
        search_target = self._proxy.open(_search_url(product))
        try:
            post_links = self._collect_search_post_links(
                search_target,
                limit_posts=limit_posts,
                exclude_reddit_ids=exclude_reddit_ids,
                max_search_scrolls=search_scrolls,
            )
            unread_links = [
                link
                for link in post_links
                if link["reddit_id"] not in exclude_reddit_ids
            ]
            skipped_count = len(post_links) - len(unread_links)
            self._report(
                f"Found {len(post_links)} candidate posts; skipped {skipped_count} already fetched; "
                f"reading up to {limit_posts} new posts."
            )
            return self._read_posts(product, unread_links[:limit_posts], comments_per_post)
        finally:
            self._proxy.close(search_target)

    def _collect_search_post_links(
        self,
        search_target: str,
        *,
        limit_posts: int,
        exclude_reddit_ids: set[str] | frozenset[str],
        max_search_scrolls: int,
    ) -> list[dict[str, str]]:
        post_links: list[dict[str, str]] = []
        for scroll_index in range(max_search_scrolls + 1):
            post_links = _unique_post_links(self._proxy.eval_json(search_target, _search_extraction_script()))
            unread_count = sum(1 for link in post_links if link["reddit_id"] not in exclude_reddit_ids)
            if unread_count >= limit_posts or scroll_index == max_search_scrolls:
                return post_links

            self._report(
                f"Loaded {len(post_links)} candidate posts ({unread_count} new); "
                f"scrolling search page {scroll_index + 1}/{max_search_scrolls}..."
            )
            self._proxy.eval_json(search_target, _search_scroll_script())
            self._sleep(SEARCH_SCROLL_WAIT_SECONDS)
        return post_links

    def _read_posts(
        self,
        product: str,
        post_links: list[dict[str, str]],
        comments_per_post: int,
    ) -> list[ContentItem]:
        items: list[ContentItem] = []
        total = len(post_links)
        for index, link in enumerate(post_links, start=1):
            self._report(f"Reading post {index}/{total}: {link['url']}")
            target_id = self._proxy.open(link["url"])
            try:
                post_payload = self._proxy.eval_json(target_id, _post_extraction_script(comments_per_post))
                items.extend(_payload_to_items(product, post_payload, comments_per_post))
            finally:
                self._proxy.close(target_id)
        return items

    def _report(self, message: str) -> None:
        if self._progress:
            self._progress(message)


def _search_url(product: str) -> str:
    query = parse.urlencode({"q": product, "type": "link", "sort": "relevance"})
    return f"{REDDIT_SEARCH_URL}?{query}"


def _estimate_search_scrolls(limit_posts: int) -> int:
    estimated = (limit_posts + POSTS_PER_SEARCH_SCROLL_ESTIMATE - 1) // POSTS_PER_SEARCH_SCROLL_ESTIMATE
    return min(MAX_AUTO_SEARCH_SCROLLS, max(MIN_AUTO_SEARCH_SCROLLS, estimated))


def _unique_post_links(rows: Any) -> list[dict[str, str]]:
    if not isinstance(rows, list):
        return []
    seen: set[str] = set()
    links: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url", "")).strip()
        match = COMMENT_PATH_RE.search(url)
        if not match:
            continue
        normalized = _normalize_reddit_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        links.append({
            "reddit_id": match.group("reddit_id"),
            "url": normalized,
            "title": str(row.get("title", "")).strip(),
        })
    return links


def _payload_to_items(product: str, payload: Any, comments_per_post: int) -> list[ContentItem]:
    if not isinstance(payload, dict):
        return []
    match = COMMENT_PATH_RE.search(str(payload.get("url", "")))
    if not match:
        return []

    subreddit = _string_or_default(payload.get("subreddit"), match.group("subreddit"))
    title = _string_or_default(payload.get("title"), "")
    post = ContentItem(
        source_type=SourceType.POST,
        reddit_id=_string_or_default(payload.get("reddit_id"), match.group("reddit_id")),
        product_name=product,
        subreddit=subreddit,
        title=title,
        text=_string_or_default(payload.get("text"), ""),
        score=_score_or_default(payload.get("score"), 0),
        url=_normalize_reddit_url(str(payload.get("url", ""))),
        created_utc=_float_or_default(payload.get("created_utc"), time.time()),
    )

    comments = [
        ContentItem(
            source_type=SourceType.COMMENT,
            reddit_id=_string_or_default(comment.get("reddit_id"), f"{post.reddit_id}-comment-{index}"),
            product_name=product,
            subreddit=subreddit,
            title=title,
            text=text,
            score=_score_or_default(comment.get("score"), 0),
            url=_normalize_reddit_url(_string_or_default(comment.get("url"), post.url)),
            created_utc=_float_or_default(comment.get("created_utc"), post.created_utc),
        )
        for index, comment in enumerate(_comment_rows(payload)[:comments_per_post], start=1)
        for text in [_string_or_default(comment.get("text"), "").strip()]
        if text
    ]
    return [post, *comments]


def _comment_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    comments = payload.get("comments", [])
    if not isinstance(comments, list):
        return []
    return [comment for comment in comments if isinstance(comment, dict)]


def _normalize_reddit_url(url: str) -> str:
    if url.startswith("/"):
        return f"https://www.reddit.com{url}"
    return url


def _string_or_default(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value)


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _score_or_default(value: Any, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if value is None:
        return default

    text = str(value).strip().replace(",", "")
    match = SCORE_TEXT_RE.search(text)
    if not match:
        return default

    number = float(match.group("number"))
    suffix = match.group("suffix").casefold()
    multiplier = {"k": 1_000, "m": 1_000_000}.get(suffix, 1)
    return int(number * multiplier)


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_target_id(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("targetId", "target_id", "id"):
            value = payload.get(key)
            if value:
                return str(value)
    return ""


def _unwrap_eval_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        if "result" in payload and isinstance(payload["result"], dict) and "value" in payload["result"]:
            return payload["result"]["value"]
        if "value" in payload:
            return payload["value"]
    return payload


def _decode_json(raw: bytes) -> Any:
    text = raw.decode("utf-8").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _search_extraction_script() -> str:
    return r"""
(() => {
  const rows = Array.from(document.querySelectorAll('a[href*="/comments/"]'))
    .map((link) => ({
      url: link.href || link.getAttribute('href') || '',
      title: (link.innerText || link.textContent || '').trim(),
    }))
    .filter((row) => row.url.includes('/comments/'));
  return JSON.stringify(rows);
})()
"""


def _search_scroll_script() -> str:
    return r"""
(() => {
  const beforeHeight = document.documentElement.scrollHeight || document.body.scrollHeight || 0;
  window.scrollTo(0, beforeHeight);
  return JSON.stringify({
    beforeHeight,
    scrollY: window.scrollY,
    viewportHeight: window.innerHeight,
  });
})()
"""


def _post_extraction_script(comments_per_post: int) -> str:
    return rf"""
(() => {{
  const parseScore = (value) => {{
    if (value === null || value === undefined) return 0;
    const text = String(value).replace(/,/g, '').trim();
    const match = text.match(/-?\d+(?:\.\d+)?\s*[kKmM]?/);
    if (!match) return 0;
    const raw = match[0].trim();
    const number = Number.parseFloat(raw);
    if (!Number.isFinite(number)) return 0;
    const suffix = raw.slice(-1).toLowerCase();
    if (suffix === 'k') return Math.trunc(number * 1000);
    if (suffix === 'm') return Math.trunc(number * 1000000);
    return Math.trunc(number);
  }};
  const scoreFromElement = (element) => {{
    if (!element) return 0;
    const attributes = ['score', 'upvotes', 'data-score', 'aria-label', 'title'];
    for (const attribute of attributes) {{
      const score = parseScore(element.getAttribute?.(attribute));
      if (score) return score;
    }}
    return parseScore(element.innerText || element.textContent || '');
  }};
  const extractPostScore = () => {{
    const post = document.querySelector('shreddit-post');
    const selectors = [
      '[data-testid="post-vote-arrows"]',
      '[slot="vote-arrows"]',
      'faceplate-number',
      'span[aria-label*="upvote" i]',
      'span[aria-label*="point" i]',
    ];
    for (const candidate of [post, ...selectors.map((selector) => document.querySelector(selector))]) {{
      const score = scoreFromElement(candidate);
      if (score) return score;
    }}
    return 0;
  }};
  const extractCommentScore = (commentNode) => {{
    const selectors = [
      '[slot="vote-arrows"]',
      'faceplate-number',
      'span[aria-label*="upvote" i]',
      'span[aria-label*="point" i]',
    ];
    for (const candidate of [commentNode, ...selectors.map((selector) => commentNode.querySelector?.(selector))]) {{
      const score = scoreFromElement(candidate);
      if (score) return score;
    }}
    return 0;
  }};
  const pathMatch = location.pathname.match(/\/r\/([^/]+)\/comments\/([^/]+)/i) || [];
  const title =
    document.querySelector('h1')?.innerText?.trim() ||
    document.querySelector('[slot="title"]')?.innerText?.trim() ||
    document.title.replace(/ : .*/, '').trim();
  const body =
    document.querySelector('[data-testid="post-content"]')?.innerText?.trim() ||
    document.querySelector('shreddit-post')?.innerText?.trim() ||
    '';
  const commentNodes = Array.from(document.querySelectorAll('shreddit-comment, [data-testid="comment"]'));
  const comments = commentNodes.slice(0, {comments_per_post}).map((node, index) => {{
    const id = node.getAttribute?.('thingid') || node.getAttribute?.('id') || `comment-${{index + 1}}`;
    const text =
      node.querySelector?.('[slot="comment"]')?.innerText?.trim() ||
      node.innerText?.trim() ||
      '';
    const permalink = node.querySelector?.('a[href*="/comments/"]')?.href || location.href;
    return {{
      reddit_id: String(id).replace(/^t1_/, ''),
      text,
      score: extractCommentScore(node),
      url: permalink,
      created_utc: Date.now() / 1000,
    }};
  }}).filter((comment) => comment.text);
  return JSON.stringify({{
    reddit_id: pathMatch[2] || location.pathname,
    subreddit: pathMatch[1] || 'unknown',
    title,
    text: body,
    score: extractPostScore(),
    url: location.href,
    created_utc: Date.now() / 1000,
    comments,
  }});
}})()
"""
