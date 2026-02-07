# Claudepad - Session Memory

## Session Summaries

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
