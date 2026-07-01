"""Server-rendered web UI: browse, search, filter, group, inline edit."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
from sqlmodel import Session, select

from ..category_tree import (
    descendant_ids,
    direct_part_counts,
    load_categories,
    ordered_with_depth,
    rollup_count,
)
from ..database import get_session
from ..models import Category, Part, utcnow
from ..search import compile_filter
from ..templating import templates

router = APIRouter(include_in_schema=False)

# Per-field advanced filters: form field name -> Part column. Each accepts a
# boolean expression (e.g. ``0603 & !0402``); see ``search.compile_filter``.
FIELD_COLUMNS = {
    "article_number": Part.article_number,
    "manufacturer": Part.manufacturer,
    "description": Part.description,
    "package": Part.package,
    "location": Part.location,
}


def _build_query(q, category_id, in_stock, fields: dict, categories: list[Category]):
    stmt = select(Part)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Part.article_number.ilike(like),
                Part.description.ilike(like),
                Part.manufacturer.ilike(like),
            )
        )
    for name, column in FIELD_COLUMNS.items():
        cond = compile_filter(fields.get(name), column)
        if cond is not None:
            stmt = stmt.where(cond)
    if category_id == "none":
        stmt = stmt.where(Part.category_id.is_(None))
    elif category_id:
        # Filtering by a top-level category includes its subcategories.
        ids = descendant_ids(categories, int(category_id))
        stmt = stmt.where(Part.category_id.in_(ids))
    if in_stock == "true":
        stmt = stmt.where(Part.quantity > 0)
    elif in_stock == "false":
        stmt = stmt.where(Part.quantity == 0)
    return stmt.order_by(Part.article_number)


def _grouped_parts(session: Session, q, category_id, in_stock, fields):
    """Parts as ordered groups: each top-level category, then its subcategories.

    Subcategory groups carry the parent name for a breadcrumb header. Groups
    with no matching parts (after filtering) are omitted.
    """
    categories = load_categories(session)
    by_id = {c.id: c for c in categories}
    parts = session.exec(
        _build_query(q, category_id, in_stock, fields, categories)
    ).all()

    buckets: dict = {}
    for part in parts:
        buckets.setdefault(part.category_id, []).append(part)

    groups = []
    for cat, depth in ordered_with_depth(categories):
        bucket = buckets.get(cat.id)
        if not bucket:
            continue
        parent = by_id.get(cat.parent_id) if depth == 1 else None
        groups.append(
            {
                "id": cat.id,
                "name": cat.name,
                "parent_name": parent.name if parent else None,
                "level": depth,
                "parts": bucket,
            }
        )

    if buckets.get(None):
        groups.append(
            {
                "id": "none",
                "name": "Uncategorized",
                "parent_name": None,
                "level": 0,
                "parts": buckets[None],
            }
        )

    return groups


def _category_options(session: Session):
    """Hierarchical options for the filter dropdown, with rollup part counts."""
    categories = load_categories(session)
    direct = direct_part_counts(session)
    return [
        {
            "id": cat.id,
            "name": cat.name,
            "depth": depth,
            "part_count": rollup_count(categories, direct, cat.id),
        }
        for cat, depth in ordered_with_depth(categories)
    ]


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: Optional[str] = None,
    category_id: Optional[str] = None,
    in_stock: Optional[str] = None,
    article_number: Optional[str] = None,
    manufacturer: Optional[str] = None,
    description: Optional[str] = None,
    package: Optional[str] = None,
    location: Optional[str] = None,
    session: Session = Depends(get_session),
):
    fields = {
        "article_number": article_number,
        "manufacturer": manufacturer,
        "description": description,
        "package": package,
        "location": location,
    }
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "groups": _grouped_parts(session, q, category_id, in_stock, fields),
            "categories": _category_options(session),
            "q": q or "",
            "category_id": category_id or "",
            "in_stock": in_stock or "",
            "fields": {k: v or "" for k, v in fields.items()},
        },
    )


@router.get("/ui/parts", response_class=HTMLResponse)
def parts_table(
    request: Request,
    q: Optional[str] = None,
    category_id: Optional[str] = None,
    in_stock: Optional[str] = None,
    article_number: Optional[str] = None,
    manufacturer: Optional[str] = None,
    description: Optional[str] = None,
    package: Optional[str] = None,
    location: Optional[str] = None,
    session: Session = Depends(get_session),
):
    fields = {
        "article_number": article_number,
        "manufacturer": manufacturer,
        "description": description,
        "package": package,
        "location": location,
    }
    return templates.TemplateResponse(
        request,
        "partials/parts_table.html",
        {"groups": _grouped_parts(session, q, category_id, in_stock, fields)},
    )


@router.patch("/ui/parts/{part_id}/quantity", response_class=HTMLResponse)
def update_quantity(
    request: Request,
    part_id: int,
    quantity: int = Form(..., ge=0),
    session: Session = Depends(get_session),
):
    part = session.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    part.quantity = quantity
    part.updated_at = utcnow()
    session.add(part)
    session.commit()
    session.refresh(part)
    return templates.TemplateResponse(
        request, "partials/quantity_cell.html", {"part": part}
    )
