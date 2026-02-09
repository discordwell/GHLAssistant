"""HTML URL rewrite helper (export-side)."""

from __future__ import annotations

from crm.assets.html import rewrite_html_asset_urls


def test_rewrite_html_asset_urls_escapes_attrs_but_not_style_tag():
    html = (
        '<img src="https://example.com/a.png?x=1&amp;y=2">'
        "<style>.x{background:url(https://example.com/a.png?x=1&y=2)}</style>"
    )
    out = rewrite_html_asset_urls(
        html,
        {"https://example.com/a.png?x=1&y=2": "https://cdn.example.com/a.png?x=1&y=2"},
        key="fetch",
    )

    assert 'src="https://cdn.example.com/a.png?x=1&amp;y=2"' in out
    assert "url(https://cdn.example.com/a.png?x=1&y=2)" in out

