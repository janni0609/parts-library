"""Shared helpers for the two-level category hierarchy.

A category with ``parent_id is None`` is top-level; otherwise it is a
subcategory of that parent. The hierarchy is limited to one level deep, so a
subcategory never has children of its own.
"""

from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from .models import Category, Part


def load_categories(session: Session) -> list[Category]:
    """All categories, name-sorted."""
    return session.exec(select(Category).order_by(Category.name)).all()


def children_by_parent(categories: list[Category]) -> dict[Optional[int], list[Category]]:
    """Map parent_id -> its child categories (name-sorted, since input is sorted)."""
    grouped: dict[Optional[int], list[Category]] = {}
    for cat in categories:
        grouped.setdefault(cat.parent_id, []).append(cat)
    return grouped


def ordered_with_depth(categories: list[Category]) -> list[tuple[Category, int]]:
    """Categories in display order: each top-level followed by its children.

    Returns (category, depth) where depth is 0 for top-level, 1 for a
    subcategory. Any category whose parent is missing/non-top-level is shown at
    the top level as a fallback so nothing silently disappears.
    """
    grouped = children_by_parent(categories)
    by_id = {c.id: c for c in categories}
    placed: set[int] = set()
    ordered: list[tuple[Category, int]] = []

    for top in grouped.get(None, []):
        ordered.append((top, 0))
        placed.add(top.id)
        for child in grouped.get(top.id, []):
            ordered.append((child, 1))
            placed.add(child.id)

    # Fallback: orphans (parent missing or itself a child) shown top-level.
    for cat in categories:
        if cat.id not in placed:
            parent = by_id.get(cat.parent_id)
            if parent is None or parent.parent_id is not None:
                ordered.append((cat, 0))
                placed.add(cat.id)

    return ordered


def flattened_with_depth(session: Session) -> list[dict]:
    """Categories as {id, name, depth} dicts in hierarchical display order."""
    return [
        {"id": cat.id, "name": cat.name, "depth": depth}
        for cat, depth in ordered_with_depth(load_categories(session))
    ]


def descendant_ids(categories: list[Category], category_id: int) -> set[int]:
    """The category itself plus the ids of its direct children."""
    ids = {category_id}
    for cat in categories:
        if cat.parent_id == category_id:
            ids.add(cat.id)
    return ids


def direct_part_counts(session: Session) -> dict[int, int]:
    """category_id -> number of parts directly assigned to it."""
    rows = session.exec(
        select(Part.category_id, func.count(Part.id)).group_by(Part.category_id)
    ).all()
    return {cid: n for cid, n in rows if cid is not None}


def rollup_count(
    categories: list[Category], direct: dict[int, int], category_id: int
) -> int:
    """Direct part count for a category plus those of its children."""
    return sum(direct.get(cid, 0) for cid in descendant_ids(categories, category_id))


def has_children(session: Session, category_id: int) -> bool:
    return (
        session.exec(
            select(Category.id).where(Category.parent_id == category_id)
        ).first()
        is not None
    )


def validate_parent(
    session: Session, parent_id: Optional[int], category_id: Optional[int] = None
) -> Optional[str]:
    """Validate a requested parent for a category.

    Enforces the two-level rule. Returns an error message, or None if valid.
    ``category_id`` is the category being edited (None when creating a new one).
    """
    if parent_id is None:
        return None
    if category_id is not None and parent_id == category_id:
        return "A category cannot be its own parent."
    parent = session.get(Category, parent_id)
    if parent is None:
        return "Selected parent category does not exist."
    if parent.parent_id is not None:
        return (
            "Subcategories can only be one level deep — "
            "pick a top-level category as the parent."
        )
    if category_id is not None and has_children(session, category_id):
        return "This category has subcategories, so it can't become a subcategory itself."
    return None
