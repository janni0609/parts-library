# Parts Library

A simple, self-hosted inventory for the electronic components you keep at home.
Track what you have — article numbers, descriptions, stock quantities, prices,
datasheets — and browse, search, and edit it all from a web page on your local
network. Designed for a small personal collection (up to ~1000 distinct parts),
so it stays deliberately lightweight: a single SQLite file and a small FastAPI
app, meant to run on an always-on Raspberry Pi.

## Features

- **Inventory tracking** — each part stores an article/part number,
  manufacturer, short description, category, package/footprint, storage
  location, quantity in stock, optional purchase price + currency, optional
  datasheet link, and free-text notes.
- **Browse, search & filter** — full table view with text search (article
  number / manufacturer / description), filter by category and in-stock vs.
  out-of-stock.
- **Group by category** — parts are grouped under collapsible category
  headers, with two levels of categories (e.g. `ICs → Opamps`). Collapsed
  state is remembered between visits.
- **Inline quantity editing** — bump stock up or down directly in the table;
  no form needed.
- **Manual add/edit** — a form to create or edit parts, including price and
  datasheet link, plus full management of the category list (add / rename /
  delete; deleting a category that still has parts is blocked).
- **CSV import with preview** — import parts from a CSV file. Existing parts
  are matched by article number (quantities/fields updated), new ones are
  inserted, and you see a preview/diff — including any unknown categories —
  before anything is committed.
- **Add parts from a photo (via the Claude app)** — instead of typing parts
  in, photograph a component, chip marking, label, or datasheet in the Claude
  app and ask Claude to extract the data into the import CSV template. No
  Anthropic API key or per-token cost — extraction happens conversationally
  under a normal Claude subscription. See
  [`.claude/skills/parts-csv-extract`](.claude/skills/parts-csv-extract/SKILL.md).

## Architecture

- **Backend** — [FastAPI](https://fastapi.tiangolo.com/) + SQLModel over a
  single SQLite database. At ~1000 rows SQLite needs no tuning, and the whole
  database is one file that's trivial to back up.
- **Frontend** — server-rendered pages using Jinja templates +
  [HTMX](https://htmx.org/) for the interactive bits (inline edits, filtering,
  import preview). No SPA, no build step.
- **Hosting** — runs as a systemd service on a Raspberry Pi 5, serving plain
  HTTP on the LAN (`uvicorn`). Access is local-only, so there's no reverse
  proxy or HTTPS.

## Project layout

```text
backend/            FastAPI app
  app/
    main.py         App entry point + /api/health
    models.py       SQLModel tables (parts, categories)
    schemas.py      Request/response validation models
    database.py     SQLite engine + init
    routers/        JSON API (parts, categories) + UI/form/import routes
    templates/      Jinja templates (base, index, forms, import, partials)
    static/         CSS, HTMX, and the import_template.csv
  scripts/
    backup_db.py    Online SQLite backup with rotation
deploy/             systemd service + backup timer units for the Raspberry Pi
.claude/skills/     parts-csv-extract — photo → CSV extraction for the Claude app
plan.md             Original design notes / project plan
```

## Running locally

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
# Windows:        .\.venv\Scripts\Activate.ps1
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000> for the web UI, or
<http://127.0.0.1:8000/docs> for the interactive API docs. The SQLite database
is created automatically at `backend/data/parts.db` on first run (it's
git-ignored — it's your data, not source).

See [`backend/README.md`](backend/README.md) for the full API endpoint
reference.

## Deploying on a Raspberry Pi

The app is meant to live on an always-on Pi on your home network, reachable
from any device at `http://<pi-hostname>.local:8000`. The
[`deploy/`](deploy/README.md) folder has the systemd unit to run it as a
service plus a timer for periodic SQLite backups, with step-by-step setup
instructions.

## Adding parts from photos

1. Open the Claude app (iOS/desktop) with this repo's `parts-csv-extract`
   skill available.
2. Photograph the part(s), label, or datasheet and ask Claude to add them to
   your parts library.
3. Claude returns a CSV matching the import template (one row per part).
4. In the web UI, go to **Import CSV**, upload the file, review the
   preview/diff, and commit.
