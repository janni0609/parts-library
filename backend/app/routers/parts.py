"""CRUD endpoints for parts, with light search/filter support."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlmodel import Session, select

from ..database import get_session
from ..models import Category, Part, utcnow
from ..schemas import PartCreate, PartRead, PartUpdate

router = APIRouter(prefix="/api/parts", tags=["parts"])


def _category_map(session: Session) -> dict[int, str]:
    rows = session.exec(select(Category.id, Category.name)).all()
    return {cid: name for cid, name in rows}


def _to_read(part: Part, category_name: Optional[str]) -> PartRead:
    return PartRead(**part.model_dump(), category_name=category_name)


def _require_valid_category(session: Session, category_id: Optional[int]) -> None:
    if category_id is not None and session.get(Category, category_id) is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Category {category_id} does not exist"
        )


@router.get("", response_model=list[PartRead])
def list_parts(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(
        default=None, description="Search article_number / description / manufacturer"
    ),
    category_id: Optional[int] = None,
    in_stock: Optional[bool] = Query(
        default=None, description="true = quantity > 0, false = out of stock"
    ),
):
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
    if category_id is not None:
        stmt = stmt.where(Part.category_id == category_id)
    if in_stock is True:
        stmt = stmt.where(Part.quantity > 0)
    elif in_stock is False:
        stmt = stmt.where(Part.quantity == 0)
    stmt = stmt.order_by(Part.article_number)

    parts = session.exec(stmt).all()
    cat_map = _category_map(session)
    return [_to_read(p, cat_map.get(p.category_id)) for p in parts]


@router.post("", response_model=PartRead, status_code=status.HTTP_201_CREATED)
def create_part(payload: PartCreate, session: Session = Depends(get_session)):
    _require_valid_category(session, payload.category_id)
    part = Part(**payload.model_dump())
    session.add(part)
    session.commit()
    session.refresh(part)
    return _to_read(part, _category_map(session).get(part.category_id))


@router.get("/{part_id}", response_model=PartRead)
def get_part(part_id: int, session: Session = Depends(get_session)):
    part = session.get(Part, part_id)
    if not part:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Part not found")
    return _to_read(part, _category_map(session).get(part.category_id))


@router.patch("/{part_id}", response_model=PartRead)
def update_part(
    part_id: int, payload: PartUpdate, session: Session = Depends(get_session)
):
    part = session.get(Part, part_id)
    if not part:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Part not found")

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        _require_valid_category(session, data["category_id"])
    for field, value in data.items():
        setattr(part, field, value)
    part.updated_at = utcnow()

    session.add(part)
    session.commit()
    session.refresh(part)
    return _to_read(part, _category_map(session).get(part.category_id))


@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_part(part_id: int, session: Session = Depends(get_session)):
    part = session.get(Part, part_id)
    if not part:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Part not found")
    session.delete(part)
    session.commit()
