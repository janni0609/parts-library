"""Request/response models (validation lives here, not on the table models)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# Shared field constraints (kept here so create/update stay consistent).
ARTICLE_MAX = 100
DESC_MAX = 500
NAME_MAX = 100


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX)
    parent_id: Optional[int] = None


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX)
    parent_id: Optional[int] = None


class CategoryRead(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    part_count: int = 0


# --------------------------------------------------------------------------- #
# Parts
# --------------------------------------------------------------------------- #
class PartBase(BaseModel):
    article_number: str = Field(min_length=1, max_length=ARTICLE_MAX)
    manufacturer: Optional[str] = Field(default=None, max_length=NAME_MAX)
    description: str = Field(min_length=1, max_length=DESC_MAX)
    category_id: Optional[int] = None
    package: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=100)
    quantity: int = Field(default=0, ge=0)
    purchase_price: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default="EUR", max_length=3)
    datasheet_url: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)


class PartCreate(PartBase):
    pass


class PartUpdate(BaseModel):
    """All fields optional: a PATCH only touches the keys actually sent."""

    article_number: Optional[str] = Field(default=None, min_length=1, max_length=ARTICLE_MAX)
    manufacturer: Optional[str] = Field(default=None, max_length=NAME_MAX)
    description: Optional[str] = Field(default=None, min_length=1, max_length=DESC_MAX)
    category_id: Optional[int] = None
    package: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=100)
    quantity: Optional[int] = Field(default=None, ge=0)
    purchase_price: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=3)
    datasheet_url: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)


class PartRead(PartBase):
    id: int
    category_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
