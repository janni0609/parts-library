"""SQLModel table definitions for the parts library.

Two tables:
- ``categories``: the managed category list (unique names).
- ``parts``: the inventory itself, each part optionally referencing a category.

Validation lives in ``schemas.py`` (request models); these table models stay
minimal because SQLModel does not run Pydantic validators on ``table=True``
models anyway.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp used for created_at / updated_at."""
    return datetime.now(timezone.utc)


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    # Self-reference: NULL = top-level category, set = subcategory of that parent.
    # Limited to one level deep (a subcategory cannot itself have children).
    parent_id: Optional[int] = Field(
        default=None, foreign_key="categories.id", index=True
    )


class Part(SQLModel, table=True):
    __tablename__ = "parts"

    id: Optional[int] = Field(default=None, primary_key=True)
    article_number: str = Field(index=True)
    manufacturer: Optional[str] = None
    description: str
    category_id: Optional[int] = Field(
        default=None, foreign_key="categories.id", index=True
    )
    package: Optional[str] = None
    location: Optional[str] = None
    quantity: int = Field(default=0)
    purchase_price: Optional[float] = None
    currency: Optional[str] = None
    datasheet_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
