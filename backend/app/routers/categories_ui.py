"""HTML page for managing the category list (add / rename / reparent / delete)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select

from ..category_tree import (
    direct_part_counts,
    has_children,
    load_categories,
    ordered_with_depth,
    validate_parent,
)
from ..database import get_session
from ..models import Category
from ..templating import templates

router = APIRouter(include_in_schema=False)


def _view_rows(session: Session) -> list[dict]:
    """Categories in display order with depth, direct part count, child flag."""
    categories = load_categories(session)
    by_id = {c.id: c for c in categories}
    direct = direct_part_counts(session)
    rows = []
    for cat, depth in ordered_with_depth(categories):
        parent = by_id.get(cat.parent_id)
        rows.append(
            {
                "id": cat.id,
                "name": cat.name,
                "depth": depth,
                "parent_id": cat.parent_id,
                "parent_name": parent.name if parent else None,
                "part_count": direct.get(cat.id, 0),
                "has_children": has_children(session, cat.id),
            }
        )
    return rows


def _top_level(session: Session) -> list[dict]:
    """Top-level categories, usable as parents in the add form."""
    return [
        {"id": c.id, "name": c.name}
        for c in load_categories(session)
        if c.parent_id is None
    ]


def _render(request: Request, session: Session, error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "categories.html",
        {
            "categories": _view_rows(session),
            "top_level": _top_level(session),
            "error": error,
        },
        status_code=status_code,
    )


def _parse_parent_id(form) -> int | None:
    raw = (form.get("parent_id") or "").strip()
    return int(raw) if raw else None


@router.get("/categories", response_class=HTMLResponse)
def categories_page(request: Request, session: Session = Depends(get_session)):
    return _render(request, session)


@router.post("/categories", response_class=HTMLResponse)
async def create_category(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name:
        return _render(request, session, "Category name is required", 422)
    if session.exec(select(Category).where(Category.name == name)).first():
        return _render(request, session, f"Category '{name}' already exists", 409)

    parent_id = _parse_parent_id(form)
    parent_error = validate_parent(session, parent_id)
    if parent_error:
        return _render(request, session, parent_error, 422)

    session.add(Category(name=name, parent_id=parent_id))
    session.commit()
    return RedirectResponse("/categories", status_code=303)


@router.post("/categories/{category_id}/edit", response_class=HTMLResponse)
async def edit_category(request: Request, category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name:
        return _render(request, session, "Category name is required", 422)

    clash = session.exec(
        select(Category).where(Category.name == name, Category.id != category_id)
    ).first()
    if clash:
        return _render(request, session, f"Category '{name}' already exists", 409)

    parent_id = _parse_parent_id(form)
    parent_error = validate_parent(session, parent_id, category_id)
    if parent_error:
        return _render(request, session, parent_error, 422)

    category.name = name
    category.parent_id = parent_id
    session.add(category)
    session.commit()
    return RedirectResponse("/categories", status_code=303)


@router.post("/categories/{category_id}/delete", response_class=HTMLResponse)
def delete_category(request: Request, category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    count = direct_part_counts(session).get(category_id, 0)
    if count > 0:
        return _render(
            request,
            session,
            f"Cannot delete '{category.name}': {count} part(s) still use it. "
            "Reassign or remove them first.",
            409,
        )
    if has_children(session, category_id):
        return _render(
            request,
            session,
            f"Cannot delete '{category.name}': it still has subcategories. "
            "Delete or move them first.",
            409,
        )

    session.delete(category)
    session.commit()
    return RedirectResponse("/categories", status_code=303)
