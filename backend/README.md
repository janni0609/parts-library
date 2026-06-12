# Parts Library — Backend (Phase 1)

FastAPI + SQLite CRUD API for the electronic parts inventory.

## Run locally (Windows)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is then at <http://127.0.0.1:8000>, with interactive docs at
<http://127.0.0.1:8000/docs>.

The SQLite database is created automatically at `backend/data/parts.db` on first
run (the file is git-ignored — it's your local data, not source).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/categories` | List categories (with `part_count`) |
| POST | `/api/categories` | Create a category (unique name) |
| GET | `/api/categories/{id}` | Get one category |
| PATCH | `/api/categories/{id}` | Rename a category |
| DELETE | `/api/categories/{id}` | Delete — **blocked** if parts still use it |
| GET | `/api/parts` | List parts; optional `?q=`, `?category_id=`, `?in_stock=` |
| POST | `/api/parts` | Create a part |
| GET | `/api/parts/{id}` | Get one part |
| PATCH | `/api/parts/{id}` | Partial update (also used for inline quantity edits) |
| DELETE | `/api/parts/{id}` | Delete a part |

## Notes

- `purchase_price` is a float; `currency` defaults to `EUR`.
- A part's `category_id` is validated on create/update — unknown ids are rejected.
- Deleting a category that still has parts returns `409` with the count.

## Deployment

For running this as a systemd service on a Raspberry Pi (with periodic SQLite
backups), see [deploy/README.md](../deploy/README.md).
