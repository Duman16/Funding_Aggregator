from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class GrantBase(BaseModel):
    title: str
    description: str | None = None
    opportunity_number: str | None = None
    agency_name: str | None = None
    posted_date: date | None = None
    deadline: date | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    status: str = "open"
    eligibility: str | None = None
    keywords: list[str] | None = None
    url: str


class GrantOut(GrantBase):
    id: UUID
    external_id: str
    source: str
    agency_code: str | None = None
    is_processed: bool
    created_at: datetime
    updated_at: datetime
    categories: list[CategoryOut] = []

    model_config = {"from_attributes": True}


class GrantListOut(BaseModel):
    items: list[GrantOut]
    total: int
    page: int
    per_page: int
    pages: int


class GrantFilter(BaseModel):
    search: str | None = None
    source: str | None = None
    status: str | None = None
    agency_name: str | None = None
    category_slug: str | None = None
    deadline_from: date | None = None
    deadline_to: date | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
