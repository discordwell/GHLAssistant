#!/usr/bin/env python3
"""Analyze captured GHL session data."""

import json
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import re


def analyze_session(filepath: str):
    """Analyze a captured session file."""
    with open(filepath) as f:
        data = json.load(f)

    print("=" * 70)
    print("GHL SESSION ANALYSIS")
    print("=" * 70)

    # Basic info
    print(f"\nProfile: {data.get('profile')}")
    print(f"Captured: {data.get('captured_at')}")
    print(f"Final URL: {data.get('page_state', {}).get('url')}")
    print(f"Page Title: {data.get('page_state', {}).get('title')}")
    print(f"Network requests: {len(data.get('network_log', [])) or data.get('network_log_count', 0)}")

    # Auth tokens
    auth = data.get("auth", {})
    if auth:
        print("\n" + "=" * 70)
        print("AUTH TOKENS")
        print("=" * 70)
        for key, value in auth.items():
            # Decode JWT if it's a token
            if key == "access_token" and value:
                import base64
                try:
                    parts = value.split(".")
                    if len(parts) == 3:
                        # Decode header
                        header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
                        # Decode payload
                        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
                        print(f"\n{key}:")
                        print(f"  Header: {header}")
                        print(f"  Payload:")
                        for k, v in payload.items():
                            print(f"    {k}: {v}")
                except Exception as e:
                    print(f"\n{key}: {value[:80]}...")
            else:
                print(f"\n{key}: {value[:80] if len(str(value)) > 80 else value}...")

    # API calls analysis
    api_calls = data.get("api_calls") or []
    network_log = data.get("network_log") or []
    if not api_calls and network_log:
        static_ext = (
            ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
            ".ttf", ".svg", ".webp", ".map", ".mp4", ".webm", ".mp3", ".zip",
        )

        def _is_static(url: str) -> bool:
            url_l = (url or "").lower()
            return any(ext in url_l for ext in static_ext)

        api_calls = [c for c in network_log if not _is_static(c.get("url", ""))]
    print("\n" + "=" * 70)
    print(f"API CALLS ({len(api_calls)} total)")
    print("=" * 70)

    # Group by domain
    by_domain = defaultdict(list)
    for call in api_calls:
        url = call.get("url", "")
        parsed = urlparse(url)
        by_domain[parsed.netloc].append(call)

    print("\nCalls by domain:")
    for domain, calls in sorted(by_domain.items(), key=lambda x: -len(x[1])):
        print(f"  {domain}: {len(calls)}")

    # Focus on GHL API
    ghl_calls = by_domain.get("backend.leadconnectorhq.com", [])

    if ghl_calls:
        print("\n" + "=" * 70)
        print(f"GHL BACKEND API ({len(ghl_calls)} calls)")
        print("=" * 70)

        # Extract unique endpoints (normalize IDs)
        endpoints = defaultdict(lambda: {"methods": set(), "count": 0, "examples": []})

        # Patterns for IDs to normalize
        id_patterns = [
            (r'/[a-zA-Z0-9]{20,}', '/{id}'),  # Long alphanumeric IDs
            (r'\?.*', ''),  # Remove query strings for grouping
        ]

        for call in ghl_calls:
            url = call.get("url", "")
            method = call.get("method", "GET")
            status = call.get("response_status", "?")

            parsed = urlparse(url)
            path = parsed.path

            # Normalize path
            normalized = path
            for pattern, replacement in id_patterns:
                normalized = re.sub(pattern, replacement, normalized)

            endpoints[normalized]["methods"].add(method)
            endpoints[normalized]["count"] += 1
            if len(endpoints[normalized]["examples"]) < 2:
                endpoints[normalized]["examples"].append({
                    "url": url,
                    "method": method,
                    "status": status
                })

        print("\nUnique endpoints (normalized):")
        for endpoint, info in sorted(endpoints.items()):
            methods = ",".join(sorted(info["methods"]))
            print(f"\n  [{methods}] {endpoint} ({info['count']}x)")
            for ex in info["examples"]:
                print(f"    → {ex['url'][:100]}")

    # Extract IDs
    print("\n" + "=" * 70)
    print("EXTRACTED IDS")
    print("=" * 70)

    ids = {
        "user_ids": set(),
        "company_ids": set(),
        "location_ids": set(),
    }

    # Extract from URLs
    for call in api_calls:
        url = call.get("url", "")

        # User ID pattern (in /users/ path)
        user_match = re.search(r'/users/([a-zA-Z0-9]+)', url)
        if user_match:
            ids["user_ids"].add(user_match.group(1))

        # Company ID pattern (in companyId param or path)
        company_match = re.search(r'companyId=([a-zA-Z0-9]+)', url)
        if company_match:
            ids["company_ids"].add(company_match.group(1))
        company_path_match = re.search(r'/companies?/([a-zA-Z0-9]+)', url)
        if company_path_match:
            ids["company_ids"].add(company_path_match.group(1))

        # Location ID pattern
        location_match = re.search(r'locationId=([a-zA-Z0-9]+)', url)
        if location_match and location_match.group(1) != "undefined":
            ids["location_ids"].add(location_match.group(1))

    for id_type, id_set in ids.items():
        if id_set:
            print(f"\n{id_type}:")
            for id_val in id_set:
                print(f"  {id_val}")

    # Check for POST requests with data
    print("\n" + "=" * 70)
    print("POST/PUT REQUESTS WITH DATA")
    print("=" * 70)

    for call in api_calls:
        if call.get("method") in ("POST", "PUT", "PATCH"):
            post_data = call.get("post_data")
            if post_data and "backend.leadconnectorhq.com" in call.get("url", ""):
                print(f"\n  {call['method']} {call['url'][:80]}")
                print(f"    Data: {post_data[:200] if post_data else 'None'}...")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default to latest session
        log_dir = Path(__file__).parent.parent / "data" / "network_logs"
        sessions = sorted(log_dir.glob("session_*.json"))
        if sessions:
            filepath = sessions[-1]
        else:
            print("No sessions found")
            sys.exit(1)
    else:
        filepath = sys.argv[1]

    analyze_session(filepath)
