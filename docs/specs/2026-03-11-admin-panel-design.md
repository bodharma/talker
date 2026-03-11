# Admin Panel Design Spec

**Date:** 2026-03-11
**Status:** Approved

## Goal

Add an admin panel at `/admin/*` for auditing sessions, reviewing safety events, viewing system stats, and managing the knowledge base. Protected by username/password login with session cookie auth. Designed to map cleanly to Phase 4 multi-user auth.

## Authentication

- Login page at `/admin/login` (GET form, POST handler)
- Credentials: `admin_username` (default: `"admin"`) and `admin_password` (required, no default) in config
- Signed session cookie via Starlette `SessionMiddleware` using existing `app_secret_key`
- All `/admin/*` routes check cookie, redirect to `/admin/login` if missing/invalid
- `/admin/logout` clears cookie

## Routes

| Route | Method | Purpose |
|---|---|---|
| `/admin/login` | GET/POST | Login form + auth handler |
| `/admin/` | GET | Session list with filters and pagination |
| `/admin/stats` | GET | System stats dashboard |
| `/admin/sessions/{id}` | GET | Session audit detail |
| `/admin/sessions/{id}/notes` | POST | Save admin notes |
| `/admin/safety` | GET | Safety event dashboard |
| `/admin/knowledge` | GET | Knowledge base management |
| `/admin/knowledge/reingest` | POST | Trigger re-ingestion |
| `/admin/logout` | GET | Clear session, redirect to login |

## Session List (`/admin/`)

Table columns: ID (truncated UUID), created date, state, instruments used, highest severity, safety event count.

Filters (query params):
- State dropdown: all, screening, follow_up, completed, abandoned
- Severity dropdown: all, minimal, mild, moderate, moderately severe, severe
- Date range: from/to date inputs
- Has safety events: checkbox

Pagination: 25 per page, server-side, prev/next links. Each row links to session detail.

## Session Audit Detail (`/admin/sessions/{id}`)

Four stacked sections:

1. **Screening Results** — Table: instrument, score, severity (color-coded), flagged items. Expandable rows for individual question answers.

2. **Conversation Transcript** — Full chat history, read-only. Safety messages highlighted yellow. Admin notes input at bottom (JSONB `admin_notes` column on sessions table).

3. **Safety Events** — Timeline: timestamp, trigger phrase, agent, message shown, resources.

4. **Voice Features** — Per-utterance table (index, role, pitch mean, jitter, shimmer, HNR, speech rate) + Chart.js line chart (pitch mean and intensity over utterances).

## Safety Dashboard (`/admin/safety`)

Reverse-chronological list of all safety events across sessions. Shows: timestamp, session ID (linked), trigger phrase, agent, message shown. Filters: date range, agent type.

## System Stats (`/admin/stats`)

Cards: total sessions, completed sessions, completion rate %, total safety events.
Charts (Chart.js): sessions by state (bar), safety events over time (line).
Table: average scores per instrument.
All computed via aggregate SQL queries.

## Knowledge Base (`/admin/knowledge`)

Table: title, source type, chunk count, ingested date. "Re-ingest" button runs `ingest_documents` async, shows success/error flash.

## DB Changes

- Add `admin_notes` column (JSONB, nullable) to `sessions` table
- One Alembic migration

## Architecture

- `talker/routes/admin.py` — all admin endpoints, auth dependency
- `talker/templates/admin/` — admin templates with `base_admin.html` (extends `base.html`, adds admin nav)
- `talker/services/admin_repo.py` — cross-session queries (safety events, stats, filtered session lists)
- Extend `SessionRepository` with aggregate methods as needed
- Chart.js via CDN script tag in admin base template
- `SessionMiddleware` added to FastAPI app in `main.py`
- Config additions: `admin_username`, `admin_password`
