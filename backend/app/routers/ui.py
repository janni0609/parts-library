"""Server-rendered web UI: browse, search, filter, group, inline edit."""

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_
from sqlmodel import Session, select

from ..database import get_session
from ..models import Category, Part, utcnow
from ..templating import templates

router = APIRouter(include_in_schema=False)


def _build_query(q: Optional[str], category_id: Optional[str], in_stock: Optional[str]):
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
    if category_id == "none":
        stmt = stmt.where(Part.category_id.is_(None))
    elif category_id:
        stmt = stmt.where(Part.category_id == int(category_id))
    if in_stock == "true":
        stmt = stmt.where(Part.quantity > 0)
    elif in_stock == "false":
        stmt = stmt.where(Part.quantity == 0)
    return stmt.order_by(Part.article_number)


def _grouped_parts(session: Session, q, category_id, in_stock):
    parts = session.exec(_build_query(q, category_id, in_stock)).all()
    cat_names = {c.id: c.name for c in session.exec(select(Category)).all()}

    grouped: dict[str, list[Part]] = {}
    for part in parts:
        name = cat_names.get(part.category_id, "Uncategorized") or "Uncategorized"
        grouped.setdefault(name, []).append(part)

    ordered = sorted(name for name in grouped if name != "Uncategorized")
    if "Uncategorized" in grouped:
        ordered.append("Uncategorized")

    return [{"name": name, "parts": grouped[name]} for name in ordered]


def _category_options(session: Session):
    rows = session.exec(
        select(Category.id, Category.name, func.count(Part.id))
        .join(Part, Part.category_id == Category.id, isouter=True)
        .group_by(Category.id, Category.name)
        .order_by(Category.name)
    ).all()
    return [{"id": cid, "name": name, "part_count": count} for cid, name, count in rows]


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: Optional[str] = None,
    category_id: Optional[str] = None,
    in_stock: Optional[str] = None,
    session: Session = Depends(get_session),
):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "groups": _grouped_parts(session, q, category_id, in_stock),
            "categories": _category_options(session),
            "q": q or "",
            "category_id": category_id or "",
            "in_stock": in_stock or "",
        },
    )


@router.get("/ui/parts", response_class=HTMLResponse)
def parts_table(
    request: Request,
    q: Optional[str] = None,
    category_id: Optional[str] = None,
    in_stock: Optional[str] = None,
    session: Session = Depends(get_session),
):
    return templates.TemplateResponse(
        request,
        "partials/parts_table.html",
        {"groups": _grouped_parts(session, q, category_id, in_stock)},
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
