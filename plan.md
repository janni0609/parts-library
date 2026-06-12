# Electronic Component Parts Library — Project Plan

Simple personal inventory system for tracking electronic components (article
numbers, descriptions, stock quantities, prices, datasheets), with a web UI
for browsing/searching. Designed for a small collection (up to ~1000 parts),
so it stays deliberately lightweight. Intended to run on an always-on
Raspberry Pi 5.


## Goals

- Track parts with: article number, manufacturer, short description, category,
  package/footprint, storage location, quantity in stock, purchase price (if
  known), datasheet link (if available)
- Web UI to browse, search, filter, and group parts by category
- Inline editing of stock quantity directly in the web viewer
- Add new parts by taking a photo with the Claude app (Pro subscription, no
  extra API costs) and having Claude fill in a standard CSV template, which
  is then imported into the library via the web UI

## Architecture

- **Backend**: FastAPI (Python) + SQLite — simple CRUD API, easy to back up
  (single file database). At ~1000 rows max, SQLite needs no tuning at all.
- **Frontend**: A single server-rendered page (HTMX + Jinja templates, or
  vanilla JS), served by the backend — table view with search/filter/group and
  inline quantity edit. No SPA build step, to keep things simple.
- **Hosting**: Runs as a systemd service on the Raspberry Pi 5, serving plain
  HTTP directly (uvicorn) on the local network. No reverse proxy / HTTPS needed
  — access is local-only, and the photo capture happens in the Claude app
  rather than in the browser, so a secure context isn't required.
- **Photo-based import**: No Anthropic API key needed. The user photographs a
  part in the Claude app (Pro subscription) and asks Claude to extract the
  data into a row matching a fixed CSV template (see below). The resulting
  CSV is then uploaded/imported via the web UI.

## Data Model (draft)

| Field | Type | Notes |
|---|---|---|
| id | integer | primary key |
| article_number | text | supplier/manufacturer part number |
| manufacturer | text, nullable | e.g. "TI", "Würth", "Vishay" |
| description | text | short description |
| category_id | integer, nullable | FK → categories table (managed list) |
| package | text, nullable | footprint, e.g. "0805", "DIP-8", "SOT-23" |
| location | text, nullable | physical storage spot, e.g. "Drawer A3" |
| quantity | integer | editable inline in UI |
| purchase_price | decimal, nullable | optional |
| currency | text, nullable | e.g. EUR |
| datasheet_url | text, nullable | optional link |
| notes | text, nullable | free text |
| created_at / updated_at | timestamp | |

**`categories` table** (managed list):

| Field | Type | Notes |
|---|---|---|
| id | integer | primary key |
| name | text, unique | e.g. "Resistors", "ICs", "Connectors" |

Parts reference a category via `category_id`. Categories are created/renamed/
deleted in the UI; deleting a category that still has parts is blocked (the UI
explains it's in use) — reassign or remove those parts first.

## Phases

### Phase 1 — Backend + Database + CRUD API
- SQLite schema + FastAPI app with endpoints for list/create/update/delete
  parts
- Basic input validation

### Phase 2 — Web UI: browse, search, filter, group
- Table/list view of parts
- Search by article number / manufacturer / description
- Filter by category, package, location, in-stock vs. out-of-stock
- Group/collapse by category
- Inline quantity editing (PATCH on change)

### Phase 3 — Manual add/edit
- Form to add/edit a part manually, including price and datasheet link
- Category management: CRUD for the managed category list (add / rename /
  delete), and a dropdown to pick a part's category from that list
- Deleting a category that still has parts is blocked; the API returns an
  error and the UI shows which/how many parts still use it

### Phase 4 — Import parts via CSV (extracted using the Claude app)
- Define a fixed CSV template with one column per data field:
  `article_number, manufacturer, description, category, package, location,
  quantity, purchase_price, currency, datasheet_url, notes`
- Workflow: take a photo of the part/label/datasheet in the Claude app (Pro
  subscription), ask Claude to fill in a row using this exact template, copy
  the result into a CSV file (one row per part, can batch multiple parts in
  one file)
  - The `category` column holds a category *name* (text). On import it's
    matched against the managed category list; unknown names are surfaced in
    the preview so you can map them to an existing category or create a new one
    (no silent auto-create).
- Web UI gets an "Import CSV" page:
  - Parses the uploaded file
  - Matches existing parts by `article_number` (updates quantity/fields if
    found, otherwise inserts a new part)
  - Shows a preview/diff before committing, including any new categories
- A blank template file (with header row + one example row) is provided in
  the repo so it's easy to reference/share with Claude when asking for the
  extraction

This avoids any Anthropic API key or per-token billing entirely — all
extraction happens conversationally in the Claude app under the existing Pro
subscription.

### Phase 5 — Raspberry Pi deployment
- systemd service for the FastAPI app (uvicorn on a fixed LAN port)
- Reach it from other devices via the Pi's hostname/IP on the local network
- SQLite file backups (e.g. periodic copy to another location)

### Phase 6 — Optional extras
- Tailscale for secure remote access to the inventory from outside the home
  network   <-- dont need that. only local for me
- iOS Shortcut to jump straight to the photo-capture page <--not needed 

## Decisions

- **Access**: Local network only. No Tailscale, no reverse proxy, plain HTTP.
- **Photo import**: Claude app + CSV import (no Anthropic API key / per-token
  cost). In-UI photo extraction via the API was considered but skipped to keep
  costs at zero.
- **Frontend**: Server-rendered single page, no SPA build step.
- **Extra fields added**: manufacturer, package/footprint, storage location.
  (Min-stock threshold considered but left out for now.)
- **Categories**: managed list (separate `categories` table), not free text.
  Deleting a category that still has parts is blocked.

## Open Questions

- Exact CSV column set/order for the import template — current draft above,
  open to tweaks once the Phase 1 schema is in place.
