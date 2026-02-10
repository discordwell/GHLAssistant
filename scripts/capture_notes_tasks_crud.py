#!/usr/bin/env python3
"""Capture GHL write endpoints for Notes + Tasks CRUD operations.

Opens a browser with network capture, navigates to a contact's Notes/Tasks
views, and programmatically performs create/edit/delete operations so we
can capture the underlying API calls.

Produces two session files:
  - session_notes_crud_*.json  (Notes create/edit/delete)
  - session_tasks_crud_*.json  (Tasks create/toggle/edit/delete)
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from maxlevel.browser.agent import BrowserAgent

# IDs from latest capture session
LOCATION_ID = "xQhURhAeK9889aDD69Fr"
CONTACT_ID = "pgeHiYeeoOTEt3AL95zl"

# Both use /v2/ format -- the older /location/ (no v2) route hangs on a spinner.
NOTES_URL = f"https://app.gohighlevel.com/v2/location/{LOCATION_ID}/contacts/detail/{CONTACT_ID}"
TASKS_URL = f"https://app.gohighlevel.com/v2/location/{LOCATION_ID}/contacts/detail/{CONTACT_ID}?view=task"

DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# JavaScript helpers
# ---------------------------------------------------------------------------

def js_click_by_text(label: str) -> str:
    """Build JS that finds and clicks an element by visible text."""
    return f"""
    (() => {{
      const query = {json.dumps(label)}.trim().toLowerCase();
      const candidates = Array.from(document.querySelectorAll(
        "button, a, [role='tab'], [role='button'], [role='menuitem'], " +
        "[aria-label], [title], span, div[class*='tab'], label"
      ));
      let best = null, bestScore = 0;
      for (const el of candidates) {{
        const hay = ((el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || '') + '').trim().toLowerCase();
        if (!hay) continue;
        let score = 0;
        if (hay === query) score += 10;
        else if (hay.startsWith(query)) score += 5;
        else if (hay.includes(query)) score += 2;
        if (score > bestScore) {{ best = el; bestScore = score; }}
      }}
      if (!best) return {{ success: false, reason: 'no_match', query }};
      try {{ best.scrollIntoView({{ block: 'center' }}); }} catch(e) {{}}
      try {{ best.focus(); }} catch(e) {{}}
      try {{ best.click(); }} catch(e) {{}}
      return {{ success: true, score: bestScore, tag: best.tagName, text: (best.innerText||'').trim().slice(0,80) }};
    }})()
    """


def js_click_selector(sel: str) -> str:
    return f"""
    (() => {{
      const el = document.querySelector({json.dumps(sel)});
      if (!el) return {{ success: false, reason: 'not_found', selector: {json.dumps(sel)} }};
      try {{ el.scrollIntoView({{ block: 'center' }}); }} catch(e) {{}}
      try {{ el.focus(); }} catch(e) {{}}
      try {{ el.click(); }} catch(e) {{}}
      return {{ success: true, tag: el.tagName, text: (el.innerText||'').trim().slice(0,80) }};
    }})()
    """


def js_type_into_focused(text: str) -> str:
    """Insert text into the currently focused/active element (input, textarea, contenteditable)."""
    return f"""
    (() => {{
      const el = document.activeElement;
      if (!el) return {{ success: false, reason: 'no_active_element' }};
      const tag = (el.tagName||'').toLowerCase();
      const editable = el.isContentEditable || el.getAttribute('contenteditable') === 'true';
      const txt = {json.dumps(text)};

      if (tag === 'input' || tag === 'textarea') {{
        // Standard form field
        el.focus();
        el.value = txt;
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return {{ success: true, method: 'value_set', tag }};
      }} else if (editable) {{
        // Content-editable (rich text editors, GHL note body, etc.)
        el.focus();
        el.innerHTML = txt;
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        return {{ success: true, method: 'contenteditable', tag }};
      }} else {{
        // Fallback: try document.execCommand
        el.focus();
        document.execCommand('insertText', false, txt);
        return {{ success: true, method: 'execCommand', tag }};
      }}
    }})()
    """


def js_type_into_selector(sel: str, text: str) -> str:
    """Set text directly into an element matched by CSS selector."""
    return f"""
    (() => {{
      const el = document.querySelector({json.dumps(sel)});
      if (!el) return {{ success: false, reason: 'not_found', selector: {json.dumps(sel)} }};
      const tag = (el.tagName||'').toLowerCase();
      const editable = el.isContentEditable || el.getAttribute('contenteditable') === 'true';
      const txt = {json.dumps(text)};

      el.focus();

      if (tag === 'input' || tag === 'textarea') {{
        el.value = txt;
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
      }} else if (editable) {{
        el.innerHTML = txt;
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
      }} else {{
        document.execCommand('insertText', false, txt);
      }}
      return {{ success: true, tag, editable }};
    }})()
    """


def js_discover_ui(kind: str) -> str:
    """Dump all interactive elements on the page for debugging.
    kind = 'notes' or 'tasks'"""
    return """
    (() => {
      const result = { buttons: [], inputs: [], contenteditable: [], role_elements: [], textareas: [] };
      document.querySelectorAll('button').forEach(el => {
        const t = (el.innerText||el.textContent||'').trim();
        if (t.length > 0 && t.length < 120) result.buttons.push({
          text: t, classes: el.className, id: el.id, disabled: el.disabled,
          ariaLabel: el.getAttribute('aria-label'), title: el.title
        });
      });
      document.querySelectorAll('input').forEach(el => {
        result.inputs.push({
          type: el.type, name: el.name, id: el.id, placeholder: el.placeholder,
          classes: el.className, value: (el.value||'').slice(0,80)
        });
      });
      document.querySelectorAll('textarea').forEach(el => {
        result.textareas.push({
          name: el.name, id: el.id, placeholder: el.placeholder,
          classes: el.className, value: (el.value||'').slice(0,80)
        });
      });
      document.querySelectorAll('[contenteditable="true"]').forEach(el => {
        result.contenteditable.push({
          tag: el.tagName, classes: el.className, id: el.id,
          text: (el.innerText||'').trim().slice(0,120)
        });
      });
      document.querySelectorAll('[role="tab"],[role="button"],[role="menuitem"],[role="dialog"],[role="menu"]').forEach(el => {
        const t = (el.innerText||el.textContent||'').trim();
        if (t.length > 0 && t.length < 120) result.role_elements.push({
          role: el.getAttribute('role'), text: t, classes: el.className, id: el.id,
          ariaSelected: el.getAttribute('aria-selected')
        });
      });
      return result;
    })()
    """


def js_find_notes_or_tasks_area() -> str:
    """Try to find the notes/tasks content area and describe its structure."""
    return """
    (() => {
      // Look for common GHL contact detail panel structures
      const panels = document.querySelectorAll(
        '[class*="note"], [class*="Note"], [class*="task"], [class*="Task"], ' +
        '[data-testid*="note"], [data-testid*="task"], ' +
        '[class*="activity"], [class*="Activity"]'
      );
      const info = [];
      panels.forEach(el => {
        info.push({
          tag: el.tagName,
          classes: el.className,
          id: el.id,
          dataTestId: el.getAttribute('data-testid'),
          childCount: el.children.length,
          text: (el.innerText||'').trim().slice(0,200)
        });
      });
      return info;
    })()
    """


# ---------------------------------------------------------------------------
# Capture helpers
# ---------------------------------------------------------------------------

def snapshot_request_ids(agent: BrowserAgent) -> set:
    calls = agent.get_api_calls(domain_filter="leadconnectorhq.com")
    return {c.get("request_id") for c in calls if isinstance(c, dict) and c.get("request_id")}


def new_calls_since(agent: BrowserAgent, baseline_ids: set) -> list[dict]:
    calls = agent.get_api_calls(domain_filter="leadconnectorhq.com")
    return [c for c in calls if isinstance(c, dict) and c.get("request_id") and c["request_id"] not in baseline_ids]


def print_calls(label: str, calls: list[dict]) -> None:
    print(f"\n--- {label} ({len(calls)} calls) ---")
    for c in calls:
        method = c.get("method", "?")
        url = c.get("url", "?")
        status = c.get("response_status", "?")
        body_preview = (c.get("request_body") or "")[:200]
        resp_preview = (c.get("response_body") or "")[:200]
        print(f"  {method} {url}  [{status}]")
        if body_preview:
            print(f"    req body: {body_preview}")
        if resp_preview:
            print(f"    res body: {resp_preview}")


async def safe_eval(agent: BrowserAgent, js: str, label: str = "eval"):
    """Evaluate JS with error logging."""
    try:
        result = await agent.evaluate(js)
        return result
    except Exception as exc:
        print(f"  [{label}] JS error: {exc}")
        return None


async def wait_and_screenshot(agent: BrowserAgent, name: str, secs: float = 2.0):
    await asyncio.sleep(secs)
    try:
        await agent.screenshot(name)
    except Exception as exc:
        print(f"  [screenshot:{name}] error: {exc}")


async def safe_screenshot(agent: BrowserAgent, name: str):
    """Non-throwing screenshot wrapper."""
    try:
        await agent.screenshot(name)
    except Exception as exc:
        print(f"  [screenshot:{name}] error: {exc}")


async def wait_for_spa_content(agent: BrowserAgent, *, timeout: float = 45.0, poll: float = 2.0) -> bool:
    """Poll until the GHL SPA has rendered meaningful content (buttons, tabs, etc.).
    
    Returns True if content appeared, False on timeout.
    """
    check_js = """
    (() => {
      const buttons = document.querySelectorAll('button');
      const tabs = document.querySelectorAll('[role="tab"]');
      const inputs = document.querySelectorAll('input, textarea, [contenteditable="true"]');
      const navItems = document.querySelectorAll('nav a, [class*="sidebar"], [class*="Sidebar"]');
      return {
        buttons: buttons.length,
        tabs: tabs.length,
        inputs: inputs.length,
        navItems: navItems.length,
        bodyLength: (document.body?.innerText || '').trim().length,
        title: document.title,
        url: window.location.href
      };
    })()
    """
    import time
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        r = await safe_eval(agent, check_js, f"spa_poll_{attempt}")
        if isinstance(r, dict):
            btns = r.get("buttons", 0) or 0
            tabs = r.get("tabs", 0) or 0
            body_len = r.get("bodyLength", 0) or 0
            print(f"  SPA poll #{attempt}: buttons={btns} tabs={tabs} bodyLen={body_len} url={r.get('url','?')[:80]}")
            # GHL contact detail typically has many buttons and tabs once loaded
            if btns >= 3 or tabs >= 1 or body_len > 200:
                print(f"  SPA content detected after {attempt} polls")
                return True
        await asyncio.sleep(poll)
    print(f"  SPA content timeout after {timeout}s")
    return False


async def bootstrap_ghl(agent: BrowserAgent) -> bool:
    """Navigate to GHL root and wait for the SPA to fully bootstrap.
    
    GHL deep-links often fail if you jump directly to a subpage
    before the SPA framework has initialised. This loads the root
    first and waits for the app shell to appear.
    
    If the session JWT has expired, GHL may sit on an infinite spinner
    instead of redirecting to login. In that case we clear the stale
    cookie and explicitly navigate to the login page.
    """
    import time

    print("Bootstrapping GHL SPA from root...")
    await agent.navigate("https://app.gohighlevel.com/")
    
    # Give the page time to render (GHL's SPA is heavy).
    print("Waiting 15s for initial page render...")
    await asyncio.sleep(15)
    
    logged_in = await agent.is_logged_in()
    
    if not logged_in:
        # Check if we're stuck on a spinner (no login form, no content).
        # If so, the JWT probably expired — clear it and go to login.
        check = await safe_eval(agent, """
        (() => {
          const bodyLen = (document.body?.innerText || '').trim().length;
          const hasPwInput = !!document.querySelector("input[type='password']");
          const buttons = document.querySelectorAll('button').length;
          return { bodyLen, hasPwInput, buttons };
        })()
        """, "login_state_check")
        
        body_len = (check or {}).get("bodyLen", 0) or 0
        has_pw = (check or {}).get("hasPwInput", False)
        btns = (check or {}).get("buttons", 0) or 0
        
        print(f"  Page state: bodyLen={body_len}, hasPwInput={has_pw}, buttons={btns}")
        
        if not has_pw and body_len < 100:
            # Stuck on spinner. Clear stale cookies and navigate to login.
            print("  Stuck on loading spinner (likely expired JWT).")
            print("  Clearing stale cookies and navigating to login page...")
            await safe_eval(agent, """
            (() => {
              // Clear m_a cookie (stale JWT)
              document.cookie = 'm_a=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=.gohighlevel.com';
              document.cookie = 'm_a=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
              return { cleared: true };
            })()
            """, "clear_cookies")
            
            await agent.navigate("https://app.gohighlevel.com/login")
            await asyncio.sleep(5)
        
        await safe_screenshot(agent, "bootstrap_login_needed")
        
        print("=" * 60)
        print("LOGIN REQUIRED")
        print("Please log in manually in the browser window.")
        print("The script will auto-detect when you're logged in")
        print("and continue with the CRUD capture.")
        print("Waiting up to 180 seconds...")
        print("=" * 60)
        
        deadline = time.time() + 180
        while time.time() < deadline:
            await asyncio.sleep(5)
            if await agent.is_logged_in():
                logged_in = True
                break
            remaining = int(deadline - time.time())
            if remaining % 15 < 5:  # Print every ~15s to avoid spam
                print(f"  Still waiting for login... ({remaining}s remaining)")
        
        if not logged_in:
            print("Login timeout. Aborting.")
            return False
    
    print("Logged in!")
    
    # After login, GHL may redirect to www.gohighlevel.com (marketing site)
    # instead of the app. Explicitly navigate to the app dashboard.
    state = await agent.get_page_state()
    current_url = state.get("url", "")
    if "app.gohighlevel.com" not in current_url:
        print(f"  Redirected to: {current_url[:100]}")
        print("  Navigating back to app.gohighlevel.com...")
        await agent.navigate("https://app.gohighlevel.com/")
        await asyncio.sleep(5)
    
    print("Waiting for SPA shell...")
    ok = await wait_for_spa_content(agent, timeout=45.0, poll=3.0)
    if not ok:
        print("  (SPA shell slow, continuing anyway)")
    return True


# ---------------------------------------------------------------------------
# NOTES CRUD
# ---------------------------------------------------------------------------

async def capture_notes_crud(agent: BrowserAgent) -> dict:
    """Navigate to Notes view and perform create / edit / delete."""
    print("\n" + "=" * 60)
    print("NOTES CRUD CAPTURE")
    print("=" * 60)

    # Navigate to contact detail (notes is the default view)
    state = await agent.navigate(NOTES_URL)
    print(f"Navigated to: {state.get('url', '?')}")
    
    # Wait for SPA content to render
    print("Waiting for contact detail to render...")
    await wait_for_spa_content(agent, timeout=30.0)
    await wait_and_screenshot(agent, "notes_01_loaded", 2)

    # Discover UI
    ui = await safe_eval(agent, js_discover_ui("notes"), "discover_ui")
    print(f"\nUI discovery: {json.dumps(ui, indent=2)[:3000]}")

    areas = await safe_eval(agent, js_find_notes_or_tasks_area(), "find_areas")
    print(f"\nNotes/Tasks areas: {json.dumps(areas, indent=2)[:2000]}")

    results = {"create": [], "edit": [], "delete": []}

    # --- CREATE NOTE ---
    print("\n>>> CREATE NOTE")
    pre_create = snapshot_request_ids(agent)

    # Try clicking "Notes" tab first to make sure we're on notes
    r = await safe_eval(agent, js_click_selector("#notes-tab"), "click_notes_tab")
    if not (isinstance(r, dict) and r.get("success")):
        r = await safe_eval(agent, js_click_by_text("Notes"), "click_notes_text")
    print(f"  Notes tab click: {r}")
    await asyncio.sleep(2)

    # Look for "Add Note", "New Note", or "+" button
    # Try multiple selectors that GHL might use
    add_note_clicked = False
    for attempt_label, attempt_js in [
        ("selector_add_note", js_click_selector('[data-testid="add-note"]')),
        ("selector_new_note", js_click_selector('[data-testid="new-note"]')),
        ("text_add_note", js_click_by_text("Add Note")),
        ("text_new_note", js_click_by_text("New Note")),
        ("text_add", js_click_by_text("Add")),
        # GHL often uses a "+" icon button near notes
        ("selector_plus", js_click_selector('button[class*="add"], button[class*="Add"], button[aria-label*="add" i]')),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Clicked add note via: {attempt_label} -> {r}")
            add_note_clicked = True
            break
    
    if not add_note_clicked:
        print("  Could not find Add Note button, trying to click in the note input area...")
        # Some GHL UIs have an always-visible textarea/contenteditable
        for sel in ['textarea[placeholder*="note" i]', 'textarea[placeholder*="Note" i]',
                     '[contenteditable="true"]', 'textarea', '.ql-editor', '.note-editor',
                     '[class*="note-input"]', '[class*="noteInput"]']:
            r = await safe_eval(agent, js_click_selector(sel), f"click_{sel}")
            if isinstance(r, dict) and r.get("success"):
                print(f"  Clicked note input: {sel} -> {r}")
                add_note_clicked = True
                break

    await asyncio.sleep(1)
    await safe_screenshot(agent, "notes_02_add_clicked")

    # Rediscover UI after clicking (modal or inline editor may have appeared)
    ui2 = await safe_eval(agent, js_discover_ui("notes"), "discover_after_add")
    print(f"\nUI after add click: {json.dumps(ui2, indent=2)[:3000]}")

    # Type note text
    note_text = f"Automated test note - {datetime.now().strftime('%H:%M:%S')}"
    typed = False
    for sel in ['.ql-editor', '[contenteditable="true"]', 'textarea[placeholder*="note" i]',
                'textarea', '[class*="note-input"]', '[class*="noteInput"]',
                '[class*="editor"]', 'div[role="textbox"]']:
        r = await safe_eval(agent, js_type_into_selector(sel, note_text), f"type_{sel}")
        if isinstance(r, dict) and r.get("success"):
            print(f"  Typed note via: {sel} -> {r}")
            typed = True
            break

    if not typed:
        # fallback: type into whatever is focused
        r = await safe_eval(agent, js_type_into_focused(note_text), "type_focused")
        print(f"  Typed into focused: {r}")

    await asyncio.sleep(1)
    await safe_screenshot(agent, "notes_03_typed")

    # Save note - click Save/Submit button
    saved = False
    for attempt_label, attempt_js in [
        ("text_save", js_click_by_text("Save")),
        ("text_add_note", js_click_by_text("Add Note")),
        ("text_submit", js_click_by_text("Submit")),
        ("text_create", js_click_by_text("Create")),
        ("selector_save", js_click_selector('button[type="submit"]')),
        ("selector_save2", js_click_selector('button[class*="save" i]')),
        ("selector_primary", js_click_selector('button[class*="primary"]')),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Save clicked via: {attempt_label} -> {r}")
            saved = True
            break

    await asyncio.sleep(3)
    await safe_screenshot(agent, "notes_04_saved")

    create_calls = new_calls_since(agent, pre_create)
    results["create"] = create_calls
    print_calls("CREATE NOTE", create_calls)

    # --- EDIT NOTE ---
    print("\n>>> EDIT NOTE")
    pre_edit = snapshot_request_ids(agent)

    # Look for edit button (pencil icon, "Edit", three-dot menu)
    edit_clicked = False
    for attempt_label, attempt_js in [
        ("text_edit", js_click_by_text("Edit")),
        ("selector_edit", js_click_selector('[data-testid*="edit"]')),
        ("selector_pencil", js_click_selector('[class*="edit"], [class*="Edit"], [aria-label*="edit" i]')),
        # Three-dot/kebab menu
        ("selector_kebab", js_click_selector('[class*="kebab"], [class*="more"], [class*="menu-trigger"], [class*="dots"]')),
        ("selector_ellipsis", js_click_selector('[aria-label*="more" i], [aria-label*="option" i], [aria-label*="menu" i]')),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Edit/menu clicked via: {attempt_label} -> {r}")
            edit_clicked = True
            await asyncio.sleep(1)
            # If we clicked a menu, now look for "Edit" option inside it
            if "kebab" in attempt_label or "ellipsis" in attempt_label or "menu" in attempt_label or "dots" in attempt_label or "more" in attempt_label:
                r2 = await safe_eval(agent, js_click_by_text("Edit"), "menu_edit")
                print(f"  Menu -> Edit: {r2}")
                await asyncio.sleep(1)
            break

    await safe_screenshot(agent, "notes_05_edit_clicked")

    if edit_clicked:
        # Type edited text
        edit_text = f"Edited note text - {datetime.now().strftime('%H:%M:%S')}"
        for sel in ['.ql-editor', '[contenteditable="true"]', 'textarea', 'div[role="textbox"]']:
            r = await safe_eval(agent, js_type_into_selector(sel, edit_text), f"edit_type_{sel}")
            if isinstance(r, dict) and r.get("success"):
                print(f"  Typed edit via: {sel}")
                break

        await asyncio.sleep(1)

        # Save edit
        for attempt_label, attempt_js in [
            ("text_save", js_click_by_text("Save")),
            ("text_update", js_click_by_text("Update")),
            ("text_submit", js_click_by_text("Submit")),
            ("selector_save", js_click_selector('button[type="submit"]')),
        ]:
            r = await safe_eval(agent, attempt_js, attempt_label)
            if isinstance(r, dict) and r.get("success"):
                print(f"  Edit save via: {attempt_label}")
                break

        await asyncio.sleep(3)

    await safe_screenshot(agent, "notes_06_edited")
    edit_calls = new_calls_since(agent, pre_edit)
    results["edit"] = edit_calls
    print_calls("EDIT NOTE", edit_calls)

    # --- DELETE NOTE ---
    print("\n>>> DELETE NOTE")
    pre_delete = snapshot_request_ids(agent)

    delete_clicked = False
    # Look for delete button or three-dot menu -> Delete
    for attempt_label, attempt_js in [
        ("text_delete", js_click_by_text("Delete")),
        ("selector_delete", js_click_selector('[data-testid*="delete"]')),
        ("selector_trash", js_click_selector('[class*="delete"], [class*="Delete"], [class*="trash"], [aria-label*="delete" i]')),
        # Three-dot menu again
        ("selector_kebab", js_click_selector('[class*="kebab"], [class*="more"], [class*="menu-trigger"], [class*="dots"]')),
        ("selector_ellipsis", js_click_selector('[aria-label*="more" i], [aria-label*="option" i], [aria-label*="menu" i]')),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Delete/menu clicked via: {attempt_label} -> {r}")
            delete_clicked = True
            await asyncio.sleep(1)
            if "kebab" in attempt_label or "ellipsis" in attempt_label or "dots" in attempt_label:
                r2 = await safe_eval(agent, js_click_by_text("Delete"), "menu_delete")
                print(f"  Menu -> Delete: {r2}")
                await asyncio.sleep(1)
            break

    # Confirm deletion if a dialog appears
    await asyncio.sleep(1)
    for lbl in ["Confirm", "Yes", "Delete", "OK", "Yes, delete"]:
        r = await safe_eval(agent, js_click_by_text(lbl), f"confirm_{lbl}")
        if isinstance(r, dict) and r.get("success"):
            print(f"  Confirmed deletion via: {lbl}")
            break

    await asyncio.sleep(3)
    await safe_screenshot(agent, "notes_07_deleted")
    delete_calls = new_calls_since(agent, pre_delete)
    results["delete"] = delete_calls
    print_calls("DELETE NOTE", delete_calls)

    return results


# ---------------------------------------------------------------------------
# TASKS CRUD
# ---------------------------------------------------------------------------

async def capture_tasks_crud(agent: BrowserAgent) -> dict:
    """Navigate to Tasks view and perform create / toggle / edit / delete."""
    print("\n" + "=" * 60)
    print("TASKS CRUD CAPTURE")
    print("=" * 60)

    state = await agent.navigate(TASKS_URL)
    print(f"Navigated to: {state.get('url', '?')}")
    
    # Wait for SPA content to render
    print("Waiting for contact detail to render...")
    await wait_for_spa_content(agent, timeout=30.0)
    await wait_and_screenshot(agent, "tasks_01_loaded", 2)

    # Make sure Tasks tab is active
    r = await safe_eval(agent, js_click_selector("#task-tab"), "click_task_tab")
    if not (isinstance(r, dict) and r.get("success")):
        r = await safe_eval(agent, js_click_by_text("Tasks"), "click_tasks_text")
    print(f"Tasks tab click: {r}")
    await asyncio.sleep(3)

    # Discover UI
    ui = await safe_eval(agent, js_discover_ui("tasks"), "discover_ui")
    print(f"\nUI discovery: {json.dumps(ui, indent=2)[:3000]}")

    results = {"create": [], "toggle": [], "edit": [], "delete": []}

    # --- CREATE TASK ---
    print("\n>>> CREATE TASK")
    pre_create = snapshot_request_ids(agent)

    task_title = f"Test task {datetime.now().strftime('%H:%M:%S')}"

    add_clicked = False
    for attempt_label, attempt_js in [
        ("selector_add_task", js_click_selector('[data-testid="add-task"]')),
        ("selector_new_task", js_click_selector('[data-testid="new-task"]')),
        ("text_add_task", js_click_by_text("Add Task")),
        ("text_new_task", js_click_by_text("New Task")),
        ("text_create_task", js_click_by_text("Create Task")),
        ("selector_plus", js_click_selector('button[class*="add" i], button[aria-label*="add" i]')),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Add task clicked via: {attempt_label} -> {r}")
            add_clicked = True
            break

    await asyncio.sleep(2)
    await safe_screenshot(agent, "tasks_02_add_clicked")

    ui2 = await safe_eval(agent, js_discover_ui("tasks"), "discover_after_add")
    print(f"\nUI after add click: {json.dumps(ui2, indent=2)[:3000]}")

    # Fill in task title
    for sel in ['input[placeholder*="task" i]', 'input[placeholder*="title" i]', 'input[name*="title" i]',
                'input[name*="task" i]', 'textarea[placeholder*="task" i]',
                'input[type="text"]', 'textarea', '[contenteditable="true"]']:
        r = await safe_eval(agent, js_type_into_selector(sel, task_title), f"task_type_{sel}")
        if isinstance(r, dict) and r.get("success"):
            print(f"  Typed task title via: {sel}")
            break

    await asyncio.sleep(1)
    await safe_screenshot(agent, "tasks_03_typed")

    # Save task
    for attempt_label, attempt_js in [
        ("text_save", js_click_by_text("Save")),
        ("text_create", js_click_by_text("Create")),
        ("text_add_task", js_click_by_text("Add Task")),
        ("text_submit", js_click_by_text("Submit")),
        ("selector_submit", js_click_selector('button[type="submit"]')),
        ("selector_primary", js_click_selector('button[class*="primary"]')),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Task save via: {attempt_label}")
            break

    await asyncio.sleep(3)
    await safe_screenshot(agent, "tasks_04_saved")
    create_calls = new_calls_since(agent, pre_create)
    results["create"] = create_calls
    print_calls("CREATE TASK", create_calls)

    # --- TOGGLE TASK (mark done/undone) ---
    print("\n>>> TOGGLE TASK")
    pre_toggle = snapshot_request_ids(agent)

    # Look for checkbox or status toggle
    toggled = False
    for attempt_label, attempt_js in [
        ("selector_checkbox", js_click_selector('input[type="checkbox"]')),
        ("selector_check_div", js_click_selector('[class*="checkbox"], [class*="Checkbox"], [role="checkbox"]')),
        ("text_mark_done", js_click_by_text("Mark as Done")),
        ("text_complete", js_click_by_text("Complete")),
        ("text_done", js_click_by_text("Done")),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Toggle (done) via: {attempt_label} -> {r}")
            toggled = True
            break

    await asyncio.sleep(2)

    # Toggle back (mark undone)
    if toggled:
        for attempt_label, attempt_js in [
            ("selector_checkbox", js_click_selector('input[type="checkbox"]')),
            ("selector_check_div", js_click_selector('[class*="checkbox"], [class*="Checkbox"], [role="checkbox"]')),
            ("text_mark_undone", js_click_by_text("Mark as Undone")),
            ("text_reopen", js_click_by_text("Reopen")),
        ]:
            r = await safe_eval(agent, attempt_js, attempt_label)
            if isinstance(r, dict) and r.get("success"):
                print(f"  Toggle (undone) via: {attempt_label} -> {r}")
                break

    await asyncio.sleep(2)
    await safe_screenshot(agent, "tasks_05_toggled")
    toggle_calls = new_calls_since(agent, pre_toggle)
    results["toggle"] = toggle_calls
    print_calls("TOGGLE TASK", toggle_calls)

    # --- EDIT TASK (e.g. due date) ---
    print("\n>>> EDIT TASK")
    pre_edit = snapshot_request_ids(agent)

    # Try clicking the task to open its edit form
    edit_clicked = False
    for attempt_label, attempt_js in [
        ("text_edit", js_click_by_text("Edit")),
        ("selector_edit", js_click_selector('[data-testid*="edit"]')),
        ("selector_pencil", js_click_selector('[class*="edit" i], [aria-label*="edit" i]')),
        # kebab menu
        ("selector_kebab", js_click_selector('[class*="kebab"], [class*="more"], [class*="menu-trigger"], [class*="dots"]')),
        ("selector_ellipsis", js_click_selector('[aria-label*="more" i], [aria-label*="option" i]')),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Edit/menu clicked via: {attempt_label}")
            edit_clicked = True
            await asyncio.sleep(1)
            if "kebab" in attempt_label or "ellipsis" in attempt_label:
                r2 = await safe_eval(agent, js_click_by_text("Edit"), "menu_edit")
                print(f"  Menu -> Edit: {r2}")
                await asyncio.sleep(1)
            break

    # Try changing due date if a date picker is visible
    if edit_clicked:
        await asyncio.sleep(1)
        ui3 = await safe_eval(agent, js_discover_ui("tasks"), "discover_edit_form")
        print(f"\nEdit form UI: {json.dumps(ui3, indent=2)[:2000]}")

        # Try clicking a due-date input
        for sel in ['input[type="date"]', 'input[name*="due" i]', 'input[placeholder*="date" i]',
                     '[class*="date-picker"]', '[class*="datePicker"]', '[class*="dueDate"]']:
            r = await safe_eval(agent, js_click_selector(sel), f"date_{sel}")
            if isinstance(r, dict) and r.get("success"):
                print(f"  Date input clicked: {sel}")
                # Set a date value
                tomorrow = (datetime.now().replace(hour=0, minute=0, second=0) 
                           + __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%d')
                await safe_eval(agent, js_type_into_selector(sel, tomorrow), "set_date")
                break

        await asyncio.sleep(1)

        # Save
        for attempt_label, attempt_js in [
            ("text_save", js_click_by_text("Save")),
            ("text_update", js_click_by_text("Update")),
            ("selector_submit", js_click_selector('button[type="submit"]')),
        ]:
            r = await safe_eval(agent, attempt_js, attempt_label)
            if isinstance(r, dict) and r.get("success"):
                print(f"  Edit save via: {attempt_label}")
                break

    await asyncio.sleep(3)
    await safe_screenshot(agent, "tasks_06_edited")
    edit_calls = new_calls_since(agent, pre_edit)
    results["edit"] = edit_calls
    print_calls("EDIT TASK", edit_calls)

    # --- DELETE TASK ---
    print("\n>>> DELETE TASK")
    pre_delete = snapshot_request_ids(agent)

    for attempt_label, attempt_js in [
        ("text_delete", js_click_by_text("Delete")),
        ("selector_delete", js_click_selector('[data-testid*="delete"]')),
        ("selector_trash", js_click_selector('[class*="delete" i], [class*="trash"], [aria-label*="delete" i]')),
        ("selector_kebab", js_click_selector('[class*="kebab"], [class*="more"], [class*="menu-trigger"], [class*="dots"]')),
        ("selector_ellipsis", js_click_selector('[aria-label*="more" i], [aria-label*="option" i]')),
    ]:
        r = await safe_eval(agent, attempt_js, attempt_label)
        if isinstance(r, dict) and r.get("success"):
            print(f"  Delete/menu clicked via: {attempt_label}")
            await asyncio.sleep(1)
            if "kebab" in attempt_label or "ellipsis" in attempt_label:
                r2 = await safe_eval(agent, js_click_by_text("Delete"), "menu_delete")
                print(f"  Menu -> Delete: {r2}")
                await asyncio.sleep(1)
            break

    # Confirm
    await asyncio.sleep(1)
    for lbl in ["Confirm", "Yes", "Delete", "OK", "Yes, delete"]:
        r = await safe_eval(agent, js_click_by_text(lbl), f"confirm_{lbl}")
        if isinstance(r, dict) and r.get("success"):
            print(f"  Confirmed via: {lbl}")
            break

    await asyncio.sleep(3)
    await safe_screenshot(agent, "tasks_07_deleted")
    delete_calls = new_calls_since(agent, pre_delete)
    results["delete"] = delete_calls
    print_calls("DELETE TASK", delete_calls)

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Use a SINGLE browser session for both phases (avoids re-bootstrap).
    async with BrowserAgent(
        profile_name="ghl_session_export",
        headless=False,
        capture_network=True,
    ) as agent:
        # Bootstrap the SPA from root first
        if not await bootstrap_ghl(agent):
            print("ABORTED: Could not log in.")
            return

        # --- NOTES session ---
        print("\n" + "#" * 60)
        print("# PHASE 1: NOTES CRUD")
        print("#" * 60)

        notes_results = await capture_notes_crud(agent)

        # Export notes session
        notes_output = str(DATA_DIR / "network_logs" / f"session_notes_crud_{ts}.json")
        await agent.export_session(notes_output)
        print(f"\nNotes session saved: {notes_output}")

        # --- TASKS session ---
        print("\n" + "#" * 60)
        print("# PHASE 2: TASKS CRUD")
        print("#" * 60)

        tasks_results = await capture_tasks_crud(agent)

        # Export tasks session
        tasks_output = str(DATA_DIR / "network_logs" / f"session_tasks_crud_{ts}.json")
        await agent.export_session(tasks_output)
        print(f"\nTasks session saved: {tasks_output}")

    # --- Summary report (outside the `async with`) ---
    report = {
        "timestamp": ts,
        "location_id": LOCATION_ID,
        "contact_id": CONTACT_ID,
        "notes": {
            "create_endpoints": len(notes_results.get("create", [])),
            "edit_endpoints": len(notes_results.get("edit", [])),
            "delete_endpoints": len(notes_results.get("delete", [])),
            "calls": notes_results,
        },
        "tasks": {
            "create_endpoints": len(tasks_results.get("create", [])),
            "toggle_endpoints": len(tasks_results.get("toggle", [])),
            "edit_endpoints": len(tasks_results.get("edit", [])),
            "delete_endpoints": len(tasks_results.get("delete", [])),
            "calls": tasks_results,
        },
    }

    report_path = DATA_DIR / "network_logs" / f"crud_capture_report_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print("CAPTURE COMPLETE")
    print(f"{'='*60}")
    print(f"Notes session:  session_notes_crud_{ts}.json")
    print(f"Tasks session:  session_tasks_crud_{ts}.json")
    print(f"Report:         crud_capture_report_{ts}.json")
    print(f"Notes create calls: {len(notes_results.get('create', []))}")
    print(f"Notes edit calls:   {len(notes_results.get('edit', []))}")
    print(f"Notes delete calls: {len(notes_results.get('delete', []))}")
    print(f"Tasks create calls: {len(tasks_results.get('create', []))}")
    print(f"Tasks toggle calls: {len(tasks_results.get('toggle', []))}")
    print(f"Tasks edit calls:   {len(tasks_results.get('edit', []))}")
    print(f"Tasks delete calls: {len(tasks_results.get('delete', []))}")


if __name__ == "__main__":
    asyncio.run(main())
