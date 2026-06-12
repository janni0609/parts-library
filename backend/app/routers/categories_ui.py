"""HTML page for managing the category list (add / rename / blocked delete)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlmodel import Session, select

from ..database import get_session
from ..models import Category, Part
from ..templating import templates

router = APIRouter(include_in_schema=False)


def _categories_with_counts(session: Session) -> list[dict]:
    rows = session.exec(
        select(Category.id, Category.name, func.count(Part.id))
        .join(Part, Part.category_id == Category.id, isouter=True)
        .group_by(Category.id, Category.name)
        .order_by(Category.name)
    ).all()
    return [{"id": cid, "name": name, "part_count": count} for cid, name, count in rows]


def _render(request: Request, session: Session, error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "categories.html",
        {"categories": _categories_with_counts(session), "error": error},
        status_code=status_code,
    )


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
    session.add(Category(name=name))
    session.commit()
    return RedirectResponse("/categories", status_code=303)


@router.post("/categories/{category_id}/rename", response_class=HTMLResponse)
async def rename_category(request: Request, category_id: int, session: Session = Depends(get_session)):
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

    category.name = name
    session.add(category)
    session.commit()
    return RedirectResponse("/categories", status_code=303)


@router.post("/categories/{category_id}/delete", response_class=HTMLResponse)
def delete_category(request: Request, category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")

    count = session.exec(
        select(func.count()).select_from(Part).where(Part.category_id == category_id)
    ).one()
    if count > 0:
        return _render(
            request,
            session,
            f"Cannot delete '{category.name}': {count} part(s) still use it. "
            "Reassign or remove them first.",
            409,
        )

    session.delete(category)
    session.commit()
    return RedirectResponse("/categories", status_code=303)
