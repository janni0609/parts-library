"""HTML pages for CSV import (Phase 4): upload, preview/diff, confirm.

Two-step flow:
1. POST /import — parse the uploaded CSV, match rows against existing parts
   by article_number, and render a preview (no DB writes yet). The parsed
   rows are staged to a JSON file on disk, keyed by a token.
2. POST /import/confirm — re-read the staged rows (plus any category mapping
   choices from the preview form) and apply them.
"""

import csv
import io
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlmodel import Session, select

from ..category_tree import flattened_with_depth, load_categories
from ..database import DATA_DIR, get_session
from ..models import Category, Part, utcnow
from ..schemas import PartCreate
from ..templating import templates

router = APIRouter(include_in_schema=False)

IMPORT_DIR = DATA_DIR / "imports"
IMPORT_DIR.mkdir(exist_ok=True)

# Fields that a re-import can update on an existing part. article_number is
# the matching key; category and quantity are handled separately below.
EDITABLE_FIELDS = [
    "manufacturer",
    "description",
    "package",
    "location",
    "purchase_price",
    "currency",
    "datasheet_url",
    "notes",
]


def _empty_to_none(value: str) -> Optional[str]:
    value = (value or "").strip()
    return value or None


def _parse_int(raw: str, field: str, errors: list[str]) -> int:
    raw = (raw or "").strip()
    if not raw:
        return 0
    try:
        value = int(raw)
    except ValueError:
        errors.append(f"{field} must be a whole number")
        return 0
    if value < 0:
        errors.append(f"{field} cannot be negative")
        return 0
    return value


def _parse_float(raw: str, field: str, errors: list[str]) -> Optional[float]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        errors.append(f"{field} must be a number")
        return None
    if value < 0:
        errors.append(f"{field} cannot be negative")
        return None
    return value


def _parse_upload(session: Session, raw: bytes) -> dict:
    """Parse uploaded CSV bytes into staged rows ready for preview/confirm."""
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    categories = load_categories(session)
    name_to_id = {c.name.strip().lower(): c.id for c in categories}
    by_id = {c.id: c for c in categories}
    existing_by_article = {p.article_number: p for p in session.exec(select(Part)).all()}

    rows: list[dict] = []
    unknown_categories: list[str] = []
    seen_unknown: set[str] = set()
    counts = {"insert": 0, "update": 0, "error": 0}

    for i, raw_row in enumerate(reader, start=2):  # row 1 is the header
        errors: list[str] = []

        article_number = (raw_row.get("article_number") or "").strip()
        description = (raw_row.get("description") or "").strip()
        if not article_number:
            errors.append("article_number is required")
        if not description:
            errors.append("description is required")

        category_name = _empty_to_none(raw_row.get("category", ""))
        category_id = None
        if category_name:
            category_id = name_to_id.get(category_name.strip().lower())
            if category_id is None and category_name not in seen_unknown:
                seen_unknown.add(category_name)
                unknown_categories.append(category_name)

        quantity = _parse_int(raw_row.get("quantity", ""), "quantity", errors)
        purchase_price = _parse_float(raw_row.get("purchase_price", ""), "purchase_price", errors)

        data = {
            "article_number": article_number,
            "manufacturer": _empty_to_none(raw_row.get("manufacturer", "")),
            "description": description,
            "category_id": category_id,
            "package": _empty_to_none(raw_row.get("package", "")),
            "location": _empty_to_none(raw_row.get("location", "")),
            "quantity": quantity,
            "purchase_price": purchase_price,
            "currency": _empty_to_none(raw_row.get("currency", "")),
            "datasheet_url": _empty_to_none(raw_row.get("datasheet_url", "")),
            "notes": _empty_to_none(raw_row.get("notes", "")),
        }

        if not errors:
            try:
                PartCreate(**{**data, "currency": data["currency"] or "EUR"})
            except ValidationError as exc:
                errors = [err["msg"] for err in exc.errors()]

        existing = existing_by_article.get(article_number) if article_number else None
        row: dict = {
            "row_num": i,
            "article_number": article_number,
            "description": description,
            "category_name": category_name,
            "data": data,
            "errors": errors,
        }

        if errors:
            row["action"] = "error"
            counts["error"] += 1
        elif existing:
            row["action"] = "update"
            row["existing_part_id"] = existing.id
            row["old_quantity"] = existing.quantity
            row["new_quantity"] = existing.quantity + quantity

            diff: dict[str, dict] = {}
            for field in EDITABLE_FIELDS:
                new_val = data[field]
                old_val = getattr(existing, field)
                if new_val is not None and new_val != old_val:
                    diff[field] = {"old": old_val, "new": new_val}

            if category_name:
                old_cat = by_id.get(existing.category_id)
                old_name = old_cat.name if old_cat else None
                if (old_name or "").strip().lower() != category_name.strip().lower():
                    diff["category"] = {"old": old_name, "new": category_name}

            row["diff"] = diff

            changes = []
            if quantity:
                changes.append(f"qty {existing.quantity} → {row['new_quantity']}")
            for field, change in diff.items():
                old_display = change["old"] if change["old"] is not None else "—"
                changes.append(f'{field}: "{old_display}" → "{change["new"]}"')
            row["changes"] = changes or ["no changes"]

            counts["update"] += 1
        else:
            row["action"] = "insert"
            row["new_quantity"] = quantity
            changes = [f"qty {quantity}"]
            if category_name:
                changes.append(f'category "{category_name}"')
            row["changes"] = changes
            counts["insert"] += 1

        rows.append(row)

    return {"rows": rows, "unknown_categories": unknown_categories, "counts": counts}


def _import_context(**overrides) -> dict:
    ctx = {"done": None, "inserted": 0, "updated": 0, "expired": None, "error": None}
    ctx.update(overrides)
    return ctx


@router.get("/import", response_class=HTMLResponse)
def import_form(
    request: Request,
    done: Optional[int] = None,
    inserted: int = 0,
    updated: int = 0,
    expired: Optional[int] = None,
):
    return templates.TemplateResponse(
        request, "import.html", _import_context(done=done, inserted=inserted, updated=updated, expired=expired)
    )


@router.post("/import", response_class=HTMLResponse)
async def import_preview(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    raw = await file.read()
    if not raw.strip():
        return templates.TemplateResponse(
            request, "import.html", _import_context(error="The uploaded file is empty."), status_code=422
        )

    try:
        staged = _parse_upload(session, raw)
    except UnicodeDecodeError:
        return templates.TemplateResponse(
            request,
            "import.html",
            _import_context(error="Could not read the file as UTF-8 text. Save the CSV as UTF-8 and try again."),
            status_code=422,
        )

    if not staged["rows"]:
        return templates.TemplateResponse(
            request, "import.html", _import_context(error="No data rows found in the CSV."), status_code=422
        )

    token = uuid.uuid4().hex
    (IMPORT_DIR / f"{token}.json").write_text(json.dumps(staged), encoding="utf-8")

    return templates.TemplateResponse(
        request,
        "import_preview.html",
        {
            "token": token,
            "rows": staged["rows"],
            "unknown_categories": staged["unknown_categories"],
            "counts": staged["counts"],
            "category_options": flattened_with_depth(session),
        },
    )


@router.post("/import/confirm", response_class=HTMLResponse)
async def confirm_import(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    token = (form.get("token") or "").strip()
    staged_path = IMPORT_DIR / f"{token}.json"
    if not token or not staged_path.exists():
        return RedirectResponse("/import?expired=1", status_code=303)

    staged = json.loads(staged_path.read_text(encoding="utf-8"))

    category_map: dict[str, Optional[int]] = {}
    for name, choice in zip(form.getlist("unknown_name"), form.getlist("category_choice")):
        if choice == "__new__":
            category = session.exec(select(Category).where(Category.name == name)).first()
            if category is None:
                category = Category(name=name, parent_id=None)
                session.add(category)
                session.flush()
            category_map[name] = category.id
        elif choice:
            category_map[name] = int(choice)
        else:
            category_map[name] = None

    inserted = updated = 0
    for row in staged["rows"]:
        if row["action"] == "error":
            continue

        data = dict(row["data"])
        category_name = row.get("category_name")
        if category_name and data.get("category_id") is None:
            data["category_id"] = category_map.get(category_name)

        if row["action"] == "insert":
            data["currency"] = data["currency"] or "EUR"
            session.add(Part(**data))
            inserted += 1
        else:
            part = session.get(Part, row["existing_part_id"])
            if part is None:
                continue
            for field, change in row["diff"].items():
                if field == "category":
                    part.category_id = data["category_id"]
                else:
                    setattr(part, field, change["new"])
            part.quantity = row["new_quantity"]
            part.updated_at = utcnow()
            session.add(part)
            updated += 1

    session.commit()
    staged_path.unlink(missing_ok=True)
    return RedirectResponse(f"/import?done=1&inserted={inserted}&updated={updated}", status_code=303)
