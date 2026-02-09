"""HTML asset discovery helpers.

Goal: extract asset URLs from funnel/page-style HTML bodies without losing the
exact raw substring (for later reversible rewrite), while also deriving a
"fetchable" URL for download jobs.
"""

from __future__ import annotations

import base64
import hashlib
import html as html_lib
import re
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import unquote_to_bytes


@dataclass(frozen=True)
class HtmlAssetCandidate:
    raw_url: str
    fetch_url: str
    usage: str
    start: int
    end: int
    context: dict[str, Any]

    @property
    def is_data_uri(self) -> bool:
        return self.fetch_url.lower().startswith("data:")


_ATTR_NAMES = (
    "src",
    "href",
    "poster",
    "data-src",
    "data-href",
    "data-poster",
)

_ATTR_URL_QUOTED_RE = re.compile(
    r"(?P<attr>" + "|".join(re.escape(a) for a in _ATTR_NAMES) + r")\s*=\s*(?P<q>['\"])(?P<value>.*?)(?P=q)",
    re.IGNORECASE | re.DOTALL,
)
_ATTR_URL_UNQUOTED_RE = re.compile(
    r"(?P<attr>" + "|".join(re.escape(a) for a in _ATTR_NAMES) + r")\s*=\s*(?P<value>[^\s>]+)",
    re.IGNORECASE,
)

_SRCSET_ATTR_QUOTED_RE = re.compile(
    r"(?P<attr>srcset|data-srcset)\s*=\s*(?P<q>['\"])(?P<value>.*?)(?P=q)",
    re.IGNORECASE | re.DOTALL,
)
_SRCSET_ATTR_UNQUOTED_RE = re.compile(
    r"(?P<attr>srcset|data-srcset)\s*=\s*(?P<value>[^\s>]+)",
    re.IGNORECASE,
)
_SRCSET_URL_PART_RE = re.compile(r"(?:^|,)\s*(?P<url>[^\s,]+)")

_STYLE_ATTR_QUOTED_RE = re.compile(
    r"style\s*=\s*(?P<q>['\"])(?P<value>.*?)(?P=q)",
    re.IGNORECASE | re.DOTALL,
)
_STYLE_ATTR_UNQUOTED_RE = re.compile(
    r"style\s*=\s*(?P<value>[^\s>]+)",
    re.IGNORECASE,
)

_STYLE_TAG_RE = re.compile(
    r"<style\b[^>]*>(?P<css>[\s\S]*?)</style\s*>",
    re.IGNORECASE,
)

_CSS_URL_RE = re.compile(
    r"url\(\s*(?P<q>['\"]?)(?P<url>[^\"')]+)(?P=q)\s*\)",
    re.IGNORECASE,
)


def _usage_for_attr(attr: str) -> str:
    a = (attr or "").strip().lower()
    if a.endswith("href"):
        return "attachment"
    return "inline_image"


def _usage_for_css_url() -> str:
    return "background"


def _normalize_fetch_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    return u


def _is_probably_asset_url(fetch_url: str, *, include_relative: bool) -> bool:
    u = (fetch_url or "").strip()
    if not u:
        return False
    lower = u.lower()
    if lower.startswith("data:"):
        return True
    if lower.startswith(("http://", "https://")):
        return True
    if u.startswith("//"):
        return True
    if include_relative:
        # Keep relative paths for later resolution if a base URL becomes available.
        if lower.startswith(("/", "./", "../")):
            return True
        if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_./-]*$", u):
            return True
    return False


def _is_ignored_url(fetch_url: str) -> bool:
    lower = (fetch_url or "").strip().lower()
    if not lower:
        return True
    if lower.startswith(("#", "mailto:", "tel:", "javascript:", "about:", "blob:", "cid:")):
        return True
    if "{{" in lower or "}}" in lower:
        return True
    return False


def iter_html_asset_candidates(html: str | None, *, include_relative: bool = False) -> Iterable[HtmlAssetCandidate]:
    """Yield URL candidates found in HTML attributes and CSS url(...).

    Notes:
      - `raw_url` is the exact substring found in the HTML source (for reversible rewrite).
      - `fetch_url` is best-effort normalized for downloading (HTML-unescaped for attribute contexts).
    """
    if not isinstance(html, str) or not html:
        return []

    candidates: list[HtmlAssetCandidate] = []

    # src/href/poster (+ data-* variants)
    for m in _ATTR_URL_QUOTED_RE.finditer(html):
        raw = (m.group("value") or "").strip()
        if not raw:
            continue
        fetch = _normalize_fetch_url(html_lib.unescape(raw))
        if _is_ignored_url(fetch):
            continue
        if not _is_probably_asset_url(fetch, include_relative=include_relative):
            continue
        candidates.append(
            HtmlAssetCandidate(
                raw_url=raw,
                fetch_url=fetch,
                usage=_usage_for_attr(m.group("attr") or ""),
                start=m.start("value"),
                end=m.end("value"),
                context={"kind": "attr", "attr": (m.group("attr") or "").lower()},
            )
        )

    for m in _ATTR_URL_UNQUOTED_RE.finditer(html):
        raw = (m.group("value") or "").strip()
        if not raw:
            continue
        fetch = _normalize_fetch_url(html_lib.unescape(raw))
        if _is_ignored_url(fetch):
            continue
        if not _is_probably_asset_url(fetch, include_relative=include_relative):
            continue
        candidates.append(
            HtmlAssetCandidate(
                raw_url=raw,
                fetch_url=fetch,
                usage=_usage_for_attr(m.group("attr") or ""),
                start=m.start("value"),
                end=m.end("value"),
                context={"kind": "attr", "attr": (m.group("attr") or "").lower()},
            )
        )

    # srcset (+ data-srcset)
    for m in _SRCSET_ATTR_QUOTED_RE.finditer(html):
        value = (m.group("value") or "")
        value_start = m.start("value")
        for sm in _SRCSET_URL_PART_RE.finditer(value):
            raw = (sm.group("url") or "").strip()
            if not raw:
                continue
            fetch = _normalize_fetch_url(html_lib.unescape(raw))
            if _is_ignored_url(fetch):
                continue
            if not _is_probably_asset_url(fetch, include_relative=include_relative):
                continue
            candidates.append(
                HtmlAssetCandidate(
                    raw_url=raw,
                    fetch_url=fetch,
                    usage="inline_image",
                    start=value_start + sm.start("url"),
                    end=value_start + sm.end("url"),
                    context={"kind": "srcset", "attr": (m.group("attr") or "").lower()},
                )
            )

    for m in _SRCSET_ATTR_UNQUOTED_RE.finditer(html):
        value = (m.group("value") or "")
        value_start = m.start("value")
        for sm in _SRCSET_URL_PART_RE.finditer(value):
            raw = (sm.group("url") or "").strip()
            if not raw:
                continue
            fetch = _normalize_fetch_url(html_lib.unescape(raw))
            if _is_ignored_url(fetch):
                continue
            if not _is_probably_asset_url(fetch, include_relative=include_relative):
                continue
            candidates.append(
                HtmlAssetCandidate(
                    raw_url=raw,
                    fetch_url=fetch,
                    usage="inline_image",
                    start=value_start + sm.start("url"),
                    end=value_start + sm.end("url"),
                    context={"kind": "srcset", "attr": (m.group("attr") or "").lower()},
                )
            )

    # style="...url(...)..."
    for m in _STYLE_ATTR_QUOTED_RE.finditer(html):
        css = m.group("value") or ""
        css_start = m.start("value")
        for cm in _CSS_URL_RE.finditer(css):
            raw = (cm.group("url") or "").strip()
            if not raw:
                continue
            fetch = _normalize_fetch_url(html_lib.unescape(raw))
            if _is_ignored_url(fetch):
                continue
            if not _is_probably_asset_url(fetch, include_relative=include_relative):
                continue
            candidates.append(
                HtmlAssetCandidate(
                    raw_url=raw,
                    fetch_url=fetch,
                    usage=_usage_for_css_url(),
                    start=css_start + cm.start("url"),
                    end=css_start + cm.end("url"),
                    context={"kind": "css_url", "where": "style_attr"},
                )
            )

    for m in _STYLE_ATTR_UNQUOTED_RE.finditer(html):
        css = m.group("value") or ""
        css_start = m.start("value")
        for cm in _CSS_URL_RE.finditer(css):
            raw = (cm.group("url") or "").strip()
            if not raw:
                continue
            fetch = _normalize_fetch_url(html_lib.unescape(raw))
            if _is_ignored_url(fetch):
                continue
            if not _is_probably_asset_url(fetch, include_relative=include_relative):
                continue
            candidates.append(
                HtmlAssetCandidate(
                    raw_url=raw,
                    fetch_url=fetch,
                    usage=_usage_for_css_url(),
                    start=css_start + cm.start("url"),
                    end=css_start + cm.end("url"),
                    context={"kind": "css_url", "where": "style_attr"},
                )
            )

    # <style> ... url(...) ... </style> (rawtext; do NOT html-unescape).
    for m in _STYLE_TAG_RE.finditer(html):
        css = m.group("css") or ""
        css_start = m.start("css")
        for cm in _CSS_URL_RE.finditer(css):
            raw = (cm.group("url") or "").strip()
            if not raw:
                continue
            fetch = _normalize_fetch_url(raw)
            if _is_ignored_url(fetch):
                continue
            if not _is_probably_asset_url(fetch, include_relative=include_relative):
                continue
            candidates.append(
                HtmlAssetCandidate(
                    raw_url=raw,
                    fetch_url=fetch,
                    usage=_usage_for_css_url(),
                    start=css_start + cm.start("url"),
                    end=css_start + cm.end("url"),
                    context={"kind": "css_url", "where": "style_tag"},
                )
            )

    # Ensure deterministic ordering for rewrite operations.
    candidates.sort(key=lambda c: (c.start, c.end, c.fetch_url))
    return candidates


def parse_data_uri(data_uri: str) -> tuple[str | None, bytes]:
    """Parse a data: URI and return (content_type, bytes)."""
    if not isinstance(data_uri, str) or not data_uri.lower().startswith("data:"):
        raise ValueError("not a data: URI")

    comma = data_uri.find(",")
    if comma < 0:
        raise ValueError("invalid data URI: missing comma")

    header = data_uri[5:comma]  # after "data:"
    payload = data_uri[comma + 1 :]

    header_parts = [p for p in header.split(";") if p]
    is_base64 = any(p.lower() == "base64" for p in header_parts)
    media_type = None
    if header_parts and "/" in header_parts[0]:
        media_type = header_parts[0]
    elif header_parts and header_parts[0].lower().startswith("text/"):
        media_type = header_parts[0]

    if is_base64:
        # Some encoders add whitespace/newlines; strip it.
        data = base64.b64decode(re.sub(r"\s+", "", payload), validate=False)
    else:
        data = unquote_to_bytes(payload)

    return media_type, data


def sha256_hex(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def rewrite_html_asset_urls(
    html: str | None,
    replacements: dict[str, str] | None,
    *,
    key: str = "fetch",
) -> str:
    """Rewrite asset URLs in an HTML string using discovered spans.

    Args:
      html: Original HTML.
      replacements: Mapping from old URL -> new URL.
      key:
        - "fetch": match using HtmlAssetCandidate.fetch_url (recommended; HTML-unescaped)
        - "raw": match using HtmlAssetCandidate.raw_url (exact substring from HTML)

    Returns:
      Updated HTML string (best-effort). For attribute contexts, replacement
      values are HTML-escaped; for <style> tag CSS (rawtext), replacements are
      left unescaped.
    """
    if not isinstance(html, str) or not html:
        return html or ""
    if not isinstance(replacements, dict) or not replacements:
        return html

    if key not in {"fetch", "raw"}:
        raise ValueError("key must be 'fetch' or 'raw'")

    candidates = list(iter_html_asset_candidates(html, include_relative=True))
    if not candidates:
        return html

    out = html
    for c in sorted(candidates, key=lambda m: (m.start, m.end), reverse=True):
        old = c.fetch_url if key == "fetch" else c.raw_url
        new = replacements.get(old)
        if not isinstance(new, str) or not new:
            continue

        ctx = c.context if isinstance(c.context, dict) else {}
        kind = ctx.get("kind")
        where = ctx.get("where")
        if kind in {"attr", "srcset"} or (kind == "css_url" and where == "style_attr"):
            new_text = html_lib.escape(new, quote=True)
        else:
            new_text = new

        out = out[: c.start] + new_text + out[c.end :]

    return out
