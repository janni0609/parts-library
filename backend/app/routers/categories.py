"""CRUD endpoints for the managed category list."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from ..database import get_session
from ..models import Category, Part
from ..schemas import CategoryCreate, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/api/categories", tags=["categories"])


def _part_count(session: Session, category_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Part).where(Part.category_id == category_id)
    ).one()


def _to_read(category: Category, part_count: int) -> CategoryRead:
    return CategoryRead(**category.model_dump(), part_count=part_count)


@router.get("", response_model=list[CategoryRead])
def list_categories(session: Session = Depends(get_session)):
    categories = session.exec(select(Category).order_by(Category.name)).all()
    rows = session.exec(
        select(Part.category_id, func.count()).group_by(Part.category_id)
    ).all()
    counts = {cid: n for cid, n in rows if cid is not None}
    return [_to_read(c, counts.get(c.id, 0)) for c in categories]


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, session: Session = Depends(get_session)):
    name = payload.name.strip()
    if session.exec(select(Category).where(Category.name == name)).first():
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Category '{name}' already exists"
        )
    category = Category(name=name)
    session.add(category)
    session.commit()
    session.refresh(category)
    return _to_read(category, 0)


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return _to_read(category, _part_count(session, category_id))


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    session: Session = Depends(get_session),
):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    name = payload.name.strip()
    clash = session.exec(
        select(Category).where(Category.name == name, Category.id != category_id)
    ).first()
    if clash:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Category '{name}' already exists"
        )
    category.name = name
    session.add(category)
    session.commit()
    session.refresh(category)
    return _to_read(category, _part_count(session, category_id))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    count = _part_count(session, category_id)
    if count > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot delete '{category.name}': {count} part(s) still use it. "
            "Reassign or remove them first.",
        )
    session.delete(category)
    session.commit()
