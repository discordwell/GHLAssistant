"""URL normalization tests for browser agents.

These tests cover the GHL deep-link rewrite behavior:
  https://app.gohighlevel.com/<route> -> https://app.gohighlevel.com/?url=<encoded>

Some routes (notably /location/... and /v2/location/...) must not be rewritten,
or the app can redirect to the wrong place (e.g. launchpad).
"""

from __future__ import annotations

from maxlevel.browser.agent import BrowserAgent
from maxlevel.browser.chrome_mcp.agent import ChromeMCPAgent


def test_browser_agent_rewrites_non_location_routes():
    agent = BrowserAgent.__new__(BrowserAgent)
    assert (
        agent._normalize_app_url("https://app.gohighlevel.com/contacts/")
        == "https://app.gohighlevel.com/?url=%2Fcontacts%2F"
    )


def test_browser_agent_does_not_rewrite_location_routes():
    agent = BrowserAgent.__new__(BrowserAgent)
    url = "https://app.gohighlevel.com/location/loc123/contacts/detail/contact456"
    assert agent._normalize_app_url(url) == url


def test_browser_agent_does_not_rewrite_v2_location_routes():
    agent = BrowserAgent.__new__(BrowserAgent)
    url = "https://app.gohighlevel.com/v2/location/loc123/contacts/detail/contact456"
    assert agent._normalize_app_url(url) == url


def test_chrome_mcp_agent_does_not_rewrite_v2_location_routes():
    agent = ChromeMCPAgent(tab_id=1)
    url = "https://app.gohighlevel.com/v2/location/loc123/contacts/detail/contact456"
    assert agent._normalize_app_url(url) == url

