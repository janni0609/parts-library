"""HTML forms for creating, editing, and deleting parts."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlmodel import Session

from ..category_tree import load_categories, ordered_with_depth
from ..database import get_session
from ..models import Category, Part, utcnow
from ..schemas import PartCreate
from ..templating import templates

router = APIRouter(include_in_schema=False)

# Defaults shown when rendering a blank "Add Part" form.
EMPTY_PART = {
    "id": None,
    "article_number": "",
    "manufacturer": None,
    "description": "",
    "category_id": None,
    "package": None,
    "location": None,
    "quantity": 0,
    "purchase_price": None,
    "currency": "EUR",
    "datasheet_url": None,
    "notes": None,
}


def _categories(session: Session):
    """Categories as {id, name, depth} in hierarchical display order."""
    return [
        {"id": cat.id, "name": cat.name, "depth": depth}
        for cat, depth in ordered_with_depth(load_categories(session))
    ]


def _empty_to_none(value: str) -> Optional[str]:
    value = value.strip()
    return value or None


def _format_errors(exc: ValidationError) -> dict[str, str]:
    return {str(err["loc"][0]): err["msg"] for err in exc.errors()}


def _parse_part_form(form) -> tuple[dict, dict[str, str]]:
    """Convert raw form strings into PartCreate-compatible types.

    Returns (data, errors) where errors covers fields that can't even be
    parsed (e.g. non-numeric quantity) before Pydantic gets a chance to run.
    """
    errors: dict[str, str] = {}
    data = {
        "article_number": form.get("article_number", "").strip(),
        "manufacturer": _empty_to_none(form.get("manufacturer", "")),
        "description": form.get("description", "").strip(),
        "package": _empty_to_none(form.get("package", "")),
        "location": _empty_to_none(form.get("location", "")),
        "currency": _empty_to_none(form.get("currency", "")) or "EUR",
        "datasheet_url": _empty_to_none(form.get("datasheet_url", "")),
        "notes": _empty_to_none(form.get("notes", "")),
    }

    category_id_raw = form.get("category_id", "")
    if category_id_raw:
        try:
            data["category_id"] = int(category_id_raw)
        except ValueError:
            errors["category_id"] = "Invalid category"
            data["category_id"] = None
    else:
        data["category_id"] = None

    quantity_raw = form.get("quantity", "")
    try:
        data["quantity"] = int(quantity_raw) if quantity_raw else 0
    except ValueError:
        errors["quantity"] = "Quantity must be a whole number"
        data["quantity"] = 0

    price_raw = form.get("purchase_price", "")
    if price_raw:
        try:
            data["purchase_price"] = float(price_raw)
        except ValueError:
            errors["purchase_price"] = "Price must be a number"
            data["purchase_price"] = None
    else:
        data["purchase_price"] = None

    return data, errors


def _validate(session: Session, data: dict, errors: dict[str, str]) -> Optional[PartCreate]:
    """Run remaining checks (category existence, Pydantic field rules).

    Mutates `errors` in place; returns a PartCreate on success, else None.
    """
    if data["category_id"] is not None and session.get(Category, data["category_id"]) is None:
        errors["category_id"] = "Selected category no longer exists"

    if errors:
        return None

    try:
        return PartCreate(**data)
    except ValidationError as exc:
        errors.update(_format_errors(exc))
        return None


@router.get("/parts/new", response_class=HTMLResponse)
def new_part_form(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request,
        "parts/form.html",
        {"mode": "create", "part": EMPTY_PART, "categories": _categories(session), "errors": {}},
    )


@router.post("/parts/new", response_class=HTMLResponse)
async def create_part(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    data, errors = _parse_part_form(form)
    payload = _validate(session, data, errors)

    if payload is None:
        return templates.TemplateResponse(
            request,
            "parts/form.html",
            {"mode": "create", "part": {**EMPTY_PART, **data}, "categories": _categories(session), "errors": errors},
            status_code=422,
        )

    part = Part(**payload.model_dump())
    session.add(part)
    session.commit()
    return RedirectResponse("/", status_code=303)


@router.get("/parts/{part_id}/edit", response_class=HTMLResponse)
def edit_part_form(request: Request, part_id: int, session: Session = Depends(get_session)):
    part = session.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    return templates.TemplateResponse(
        request,
        "parts/form.html",
        {"mode": "edit", "part": part, "categories": _categories(session), "errors": {}},
    )


@router.post("/parts/{part_id}/edit", response_class=HTMLResponse)
async def update_part(request: Request, part_id: int, session: Session = Depends(get_session)):
    part = session.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")

    form = await request.form()
    data, errors = _parse_part_form(form)
    payload = _validate(session, data, errors)

    if payload is None:
        return templates.TemplateResponse(
            request,
            "parts/form.html",
            {"mode": "edit", "part": {**data, "id": part_id}, "categories": _categories(session), "errors": errors},
            status_code=422,
        )

    for field, value in payload.model_dump().items():
        setattr(part, field, value)
    part.updated_at = utcnow()
    session.add(part)
    session.commit()
    return RedirectResponse("/", status_code=303)


@router.post("/parts/{part_id}/delete")
def delete_part(part_id: int, session: Session = Depends(get_session)):
    part = session.get(Part, part_id)
    if not part:
        raise HTTPException(404, "Part not found")
    session.delete(part)
    session.commit()
    return RedirectResponse("/", status_code=303)
