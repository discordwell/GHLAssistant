# Claudepad - Session Memory

## Session Summaries

### 2026-02-07T~09:00 UTC - Workflow Builder + Execution Engine + AI Chat
- Resumed from context-limited session (rename was already done)
- Ran execution engine tests (62 passed), confirmed all prior work solid
- Built AI Chat: `chat_svc.py` (Claude API + 11 tools + SSE streaming), `chat.py` router, chat UI template
- Built Webhooks + Triggers: `webhooks.py` router, `trigger_svc.py` (GHL event mapping, filter matching)
- Code review identified 10 issues; fixed HIGH priority ones:
  - API routes returning `(dict, 404)` tuple -> `HTTPException` (3 endpoints)
  - Webhook errors returning 200 -> proper HTTP status codes
  - Infinite loop in runner -> cycle detection via visited set
  - XSS in Drawflow node HTML -> `esc()` function for HTML escaping
  - Chat tool loop unbounded -> max 10 rounds limit
- 91 workflow tests, 520 total across all suites, all passing
- Committed & pushed: `6c2f4de Add workflow builder with visual editor, execution engine, AI chat, and webhooks`

### 2026-02-06T~23:00 UTC - Hiring Tool Manual Testing & Bug Fix
- Completed full browser automation testing of hiring tool web app (port 8080)
- Tested: positions, candidates, kanban board, interviews, analytics, sync
- Found & fixed bug: Kanban cards showed "Position #1" instead of title
- Fix: Added `position_map` to all 3 board routes + Jinja2 conditional lookup
- Committed & pushed: `7f6cf4b Show position title instead of ID on Kanban board cards`
- All 45 hiring + 336 existing tests pass
- Saved learnings to MEMORY.md and hiring_tool_notes.md

### 2026-02-06T~20:00 UTC - Hiring Tool Web App Implementation
- Built full standalone hiring tool at `hiring_tool/` (41 files)
- FastAPI + HTMX + Jinja2 + Tailwind + SortableJS + SQLite
- 6 models, 6 routers, 3 services, 45 tests
- Added `ghl hiring serve` CLI command
- Code review approved, committed & pushed

### 2026-02-06T~15:00 UTC - Hiring Funnel CLI Commands
- Built `src/maxlevel/hiring/` package (template.py, guide.py)
- 8 CLI commands for hiring pipeline management
- Blueprint defines tags, custom fields, custom values, pipeline
- 65 tests (34 template + 31 CLI), all passing

## Key Findings

- Jinja2 dict lookup: use `{% if key in dict %}` not `.get()` - see memory/hiring_tool_notes.md
- Uvicorn `--reload` needed for Python changes; templates reload automatically
- `{% include %}` inherits parent context in Jinja2
- StaticPool + check_same_thread=False for SQLite test fixtures with FastAPI TestClient
- Server background task pattern: start with `run_in_background=True`, check with `TaskOutput`
