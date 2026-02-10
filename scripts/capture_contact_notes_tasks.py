#!/usr/bin/env python3
"""Capture GHL contact detail Notes/Tasks API endpoints via browser automation.

This script is intended to be a quick "endpoint spelunker": it opens a logged-in
Chrome profile, navigates to a contact, clicks the Notes and Tasks UI, and then
exports a `session_*.json` capture for analysis.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx

from maxlevel.browser.agent import BrowserAgent


def _build_click_by_text_js(label: str) -> str:
    label_json = json.dumps(label)
    return f"""
(() => {{
  const query = String({label_json} || "").trim().toLowerCase();
  if (!query) return {{ success: false, reason: "empty_query" }};

  const candidates = Array.from(document.querySelectorAll(
    "button,a,[role='tab'],[role='button'],[aria-label],[title]"
  ));

  function textOf(el) {{
    return ((el.innerText || el.textContent || el.getAttribute("aria-label") || el.getAttribute("title") || "") + "")
      .trim();
  }}

  let best = null;
  let bestScore = 0;
  for (const el of candidates) {{
    const text = textOf(el);
    const hay = text.toLowerCase();
    if (!hay) continue;

    let score = 0;
    if (hay === query) score += 5;
    if (hay.includes(query)) score += 2;
    for (const token of query.split(/\\s+/).filter(Boolean)) {{
      if (hay.includes(token)) score += 1;
    }}

    if (score > bestScore) {{
      best = el;
      bestScore = score;
    }}
  }}

  if (!best || bestScore <= 0) {{
    return {{ success: false, reason: "no_match" }};
  }}

  try {{ best.scrollIntoView({{ behavior: "auto", block: "center" }}); }} catch (e) {{}}
  try {{ if (typeof best.focus === "function") best.focus(); }} catch (e) {{}}
  try {{ if (typeof best.click === "function") best.click(); }} catch (e) {{}}

  return {{
    success: true,
    score: bestScore,
    tag: best.tagName || "",
    text: textOf(best).slice(0, 120)
  }};
}})()
"""


def _build_click_by_selector_js(selector: str) -> str:
    selector_json = json.dumps(selector)
    return f"""
(() => {{
  const sel = String({selector_json} || "").trim();
  if (!sel) return {{ success: false, reason: "empty_selector" }};

  const el = document.querySelector(sel);
  if (!el) return {{ success: false, reason: "not_found", selector: sel }};

  function textOf(node) {{
    return ((node.innerText || node.textContent || node.getAttribute?.("aria-label") || node.getAttribute?.("title") || "") + "")
      .trim();
  }}

  try {{ el.scrollIntoView({{ behavior: "auto", block: "center" }}); }} catch (e) {{}}
  try {{ if (typeof el.focus === "function") el.focus(); }} catch (e) {{}}
  try {{ if (typeof el.click === "function") el.click(); }} catch (e) {{
    return {{ success: false, reason: String(e), selector: sel }};
  }}

  return {{
    success: true,
    selector: sel,
    tag: el.tagName || "",
    id: el.id || null,
    role: el.getAttribute?.("role") || null,
    text: textOf(el).slice(0, 120)
  }};
}})()
"""


async def capture_contact_page(*, profile: str, headless: bool) -> dict:
    """Navigate to GHL contact page and capture Notes/Tasks structure."""
    
    async with BrowserAgent(
        profile_name=profile,
        headless=headless,
        capture_network=True
    ) as agent:
        # Step 1: Navigate to GHL
        print("\n=== Step 1: Navigating to GHL ===")
        state = await agent.navigate("https://app.gohighlevel.com/")
        print(f"Page loaded: {state.get('title', 'Unknown')}")
        print(f"URL: {state.get('url', 'Unknown')}")
        
        # Take initial screenshot
        await agent.screenshot("01_ghl_home")
        
        # Step 2: Check if logged in
        print("\n=== Step 2: Checking login status ===")
        logged_in = await agent.is_logged_in()
        print(f"Logged in: {logged_in}")
        
        if not logged_in:
            print("\n❌ Not logged in. Please log in manually in the browser.")
            print("Waiting 60 seconds for manual login...")
            await asyncio.sleep(60)
            
            # Check again
            logged_in = await agent.is_logged_in()
            if not logged_in:
                print("Still not logged in. Exiting.")
                return
        
        print("✅ Logged in successfully")
        
        def _infer_location_id_from_sessions() -> str | None:
            logs_dir = Path(__file__).parent.parent / "data" / "network_logs"
            if not logs_dir.exists():
                return None

            candidates: list[tuple[float, str]] = []
            for path in logs_dir.glob("session_*.json"):
                try:
                    data = json.load(open(path))
                except Exception:
                    continue

                auth = data.get("auth") or {}
                if isinstance(auth, dict):
                    lid = auth.get("locationId")
                    if isinstance(lid, str) and lid:
                        try:
                            candidates.append((path.stat().st_mtime, lid))
                        except Exception:
                            candidates.append((0.0, lid))

            if not candidates:
                return None

            candidates.sort(key=lambda x: x[0])
            return candidates[-1][1]

        def _infer_location_id() -> str | None:
            env_lid = os.getenv("GHL_LOCATION_ID")
            if isinstance(env_lid, str) and env_lid.strip():
                return env_lid.strip()

            # Prefer recent captured sessions: they're most likely to reflect the
            # currently-selected location in the browser profile.
            lid = _infer_location_id_from_sessions()
            if lid:
                return lid

            # Fall back to ~/.ghl/tokens.json (may be stale if you haven't run auth quick recently).
            try:
                tokens_file = Path.home() / ".ghl" / "tokens.json"
                if tokens_file.exists():
                    data = json.load(open(tokens_file))
                    session = (data or {}).get("session") or {}
                    if isinstance(session, dict):
                        lid = session.get("location_id")
                        if isinstance(lid, str) and lid:
                            return lid
            except Exception:
                pass

            return None

        async def _fetch_first_contact_id(*, token: str, location_id: str) -> str | None:
            headers = {
                "Authorization": f"Bearer {token}",
                "version": "2021-07-28",
                "channel": "APP",
                "source": "WEB_USER",
            }
            async with httpx.AsyncClient(
                base_url="https://backend.leadconnectorhq.com",
                headers=headers,
                timeout=30.0,
            ) as client:
                resp = await client.get("/contacts/", params={"locationId": location_id, "limit": 1})
                if resp.status_code != 200:
                    raise RuntimeError(f"/contacts/ failed: {resp.status_code} {resp.text[:200]}")
                payload = resp.json() if resp.content else {}
                contacts = payload.get("contacts")
                if not isinstance(contacts, list) or not contacts:
                    return None
                first = contacts[0] if isinstance(contacts[0], dict) else {}
                cid = first.get("id") or first.get("_id")
                return cid if isinstance(cid, str) and cid else None

        # Step 3: Determine location id (needed for reliable contact routing).
        print("\n=== Step 3: Determining Location ID ===")
        location_id = _infer_location_id()
        print(f"Location ID: {location_id or 'UNKNOWN'}")

        if not location_id:
            print("⚠️  Could not infer location id. Will attempt manual navigation later.")

        # Step 4: Resolve a contact id via API (much more reliable than DOM scraping).
        print("\n=== Step 4: Fetching a contact id ===")
        cookie_auth = await agent.extract_cookie_auth()
        token = cookie_auth.get("access_token") if isinstance(cookie_auth, dict) else None
        contact_id: str | None = None

        if isinstance(token, str) and token and isinstance(location_id, str) and location_id:
            try:
                contact_id = await _fetch_first_contact_id(token=token, location_id=location_id)
            except Exception as exc:
                print(f"⚠️  Failed to fetch contacts via API: {exc}")
                contact_id = None

        if not contact_id:
            print("⚠️  Could not fetch a contact id. You may need to create one first or navigate manually.")
            print("Waiting 30 seconds for manual navigation to a contact detail page...")
            await asyncio.sleep(30)
        else:
            print(f"Contact ID: {contact_id}")

        # Step 5: Navigate to contact detail
        print("\n=== Step 5: Navigating to Contact Detail ===")
        if contact_id and location_id:
            # Use /v2/location/... for contact detail; /location/... often 404s.
            contact_url = f"https://app.gohighlevel.com/v2/location/{location_id}/contacts/detail/{contact_id}"
            print(f"Opening contact: {contact_url}")
            await agent.navigate(contact_url)
            await asyncio.sleep(3)
        else:
            print("Manual mode: please navigate to a specific contact's detail page now...")
            await asyncio.sleep(15)
        
        # Capture contact detail page
        print("\n=== Step 6: Analyzing contact detail page ===")
        await agent.screenshot("03_contact_detail")
        
        # Get page structure
        page_structure_js = """
        (() => {
            const structure = {
                url: window.location.href,
                title: document.title,
                tabs: [],
                sections: [],
                buttons: []
            };
            
            // Look for tabs (common patterns)
            const tabSelectors = [
                '[role="tab"]',
                '.tab',
                '[class*="tab"]',
                'button[class*="Tab"]',
                'div[class*="tab-"]'
            ];
            
            for (const selector of tabSelectors) {
                const tabs = document.querySelectorAll(selector);
                tabs.forEach(tab => {
                    const text = (tab.innerText || tab.textContent || '').trim();
                    if (text && text.length < 50) {
                        structure.tabs.push({
                            text,
                            selector,
                            classes: tab.className,
                            role: tab.getAttribute('role'),
                            ariaSelected: tab.getAttribute('aria-selected')
                        });
                    }
                });
            }
            
            // Look for sections with "Notes" or "Tasks"
            const allElements = document.querySelectorAll('*');
            allElements.forEach(el => {
                const text = (el.innerText || el.textContent || '').toLowerCase();
                if ((text.includes('notes') || text.includes('tasks')) && text.length < 100) {
                    structure.sections.push({
                        tag: el.tagName,
                        text: (el.innerText || el.textContent || '').trim().substring(0, 100),
                        classes: el.className,
                        id: el.id
                    });
                }
            });
            
            // Look for buttons
            const buttons = document.querySelectorAll('button');
            buttons.forEach(btn => {
                const text = (btn.innerText || btn.textContent || '').trim();
                if (text && text.length < 50) {
                    structure.buttons.push({
                        text,
                        classes: btn.className
                    });
                }
            });
            
            return structure;
        })()
        """
        
        page_structure = await agent.evaluate(page_structure_js)
        print("\n📋 Page Structure:")
        print(json.dumps(page_structure, indent=2))

        # Baseline API calls before clicking Notes/Tasks (don't clear logs; just diff).
        baseline_api_calls = agent.get_api_calls(domain_filter="leadconnectorhq.com")
        baseline_request_ids = {
            c.get("request_id")
            for c in baseline_api_calls
            if isinstance(c, dict) and c.get("request_id")
        }
        
        # Step 7: Try to find and click Notes tab
        print("\n=== Step 7: Looking for Notes tab ===")
        
        # NOTE: Don't clear the network log here. Notes/Tasks endpoints may be
        # triggered during initial page load, and clearing would also destroy
        # useful debugging context if the click fails.
        
        # Prefer the known contact detail tab id; fall back to fuzzy text.
        notes_click = await agent.evaluate(_build_click_by_selector_js("#notes-tab"))
        if not (isinstance(notes_click, dict) and notes_click.get("success")):
            notes_click = await agent.evaluate(_build_click_by_text_js("Notes"))
        print(f"Notes click result: {notes_click}")
        
        if isinstance(notes_click, dict) and notes_click.get('success'):
            await asyncio.sleep(2)  # Wait for Notes to load
            await agent.screenshot("04_notes_section")
            print("✅ Notes section opened")
        else:
            print("⚠️  Could not find Notes tab")

        # Snapshot API calls after Notes is opened (before navigating elsewhere).
        after_notes_calls = agent.get_api_calls(domain_filter="leadconnectorhq.com")
        notes_endpoints = [
            c
            for c in after_notes_calls
            if isinstance(c, dict)
            and c.get("request_id")
            and c.get("request_id") not in baseline_request_ids
        ]
        after_notes_request_ids = {
            c.get("request_id")
            for c in after_notes_calls
            if isinstance(c, dict) and c.get("request_id")
        }

        # Step 8: Try to find and click Tasks tab
        print("\n=== Step 8: Looking for Tasks tab ===")
        
        # Prefer the known contact detail tab id; fall back to fuzzy text.
        tasks_click = await agent.evaluate(_build_click_by_selector_js("#task-tab"))
        if not (isinstance(tasks_click, dict) and tasks_click.get("success")):
            tasks_click = await agent.evaluate(_build_click_by_text_js("Tasks"))
        print(f"Tasks click result: {tasks_click}")
        
        if isinstance(tasks_click, dict) and tasks_click.get('success'):
            await asyncio.sleep(2)  # Wait for Tasks to load
            await agent.screenshot("05_tasks_section")
            print("✅ Tasks section opened")
        else:
            print("⚠️  Could not find Tasks tab")

        # Step 9: Analyze captured API calls
        print("\n=== Step 9: Analyzing captured API calls ===")

        api_calls = agent.get_api_calls(domain_filter="leadconnectorhq.com")
        # Calls attributable to the Tasks click = calls observed after the Notes snapshot.
        tasks_endpoints = [
            c
            for c in api_calls
            if isinstance(c, dict)
            and c.get("request_id")
            and c.get("request_id") not in after_notes_request_ids
        ]
        
        print(f"\n📝 Notes-related API calls ({len(notes_endpoints)}):")
        for call in notes_endpoints:
            print(f"  {call['method']} {call['url']}")
            print(f"    Status: {call.get('response_status')}")
            if call.get('response_body'):
                print(f"    Response preview: {call['response_body'][:200]}...")
        
        print(f"\n✅ Tasks-related API calls ({len(tasks_endpoints)}):")
        for call in tasks_endpoints:
            print(f"  {call['method']} {call['url']}")
            print(f"    Status: {call.get('response_status')}")
            if call.get('response_body'):
                print(f"    Response preview: {call['response_body'][:200]}...")
        
        # Export session
        print("\n=== Step 10: Exporting session data ===")
        session_file = await agent.export_session()
        print(f"✅ Session exported to: {session_file}")
        
        # Create a summary report
        report = {
            "logged_in": logged_in,
            "location_id": location_id,
            "contact_id": contact_id,
            "contact_page_structure": page_structure,
            "notes_tab_found": bool(notes_click.get('success', False)) if isinstance(notes_click, dict) else False,
            "tasks_tab_found": bool(tasks_click.get('success', False)) if isinstance(tasks_click, dict) else False,
            "notes_endpoints": notes_endpoints,
            "tasks_endpoints": tasks_endpoints,
            "all_api_calls": api_calls,
            "screenshots": agent.screenshots
        }
        
        report_file = Path(__file__).parent.parent / "data" / "contact_notes_tasks_report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📊 Report saved to: {report_file}")
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"✅ Logged in: {logged_in}")
        print(f"✅ Notes tab found: {bool(notes_click.get('success', False)) if isinstance(notes_click, dict) else False}")
        print(f"✅ Tasks tab found: {bool(tasks_click.get('success', False)) if isinstance(tasks_click, dict) else False}")
        print(f"📝 Notes API endpoints: {len(notes_endpoints)}")
        print(f"✅ Tasks API endpoints: {len(tasks_endpoints)}")
        print(f"📸 Screenshots: {len(agent.screenshots)}")
        print("="*60)
        
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="ghl_session_export", help="Browser profile name")
    parser.add_argument("--headless", action="store_true", help="Run headless (no UI window)")
    args = parser.parse_args()

    asyncio.run(capture_contact_page(profile=args.profile, headless=bool(args.headless)))
