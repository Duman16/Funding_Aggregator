from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, HttpUrl, Field


class CategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class GrantBase(BaseModel):
    title: str
    description: Optional[str] = None
    opportunity_number: Optional[str] = None
    agency_name: Optional[str] = None
    posted_date: Optional[date] = None
    deadline: Optional[date] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    status: str = "open"
    eligibility: Optional[str] = None
    keywords: Optional[List[str]] = None
    url: str


class GrantOut(GrantBase):
    id: UUID
    external_id: str
    source: str
    agency_code: Optional[str] = None
    is_processed: bool
    created_at: datetime
    updated_at: datetime
    categories: List[CategoryOut] = []

    model_config = {"from_attributes": True}


class GrantListOut(BaseModel):
    items: List[GrantOut]
    total: int
    page: int
    per_page: int
    pages: int


class GrantFilter(BaseModel):
    search: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    agency_name: Optional[str] = None
    category_slug: Optional[str] = None
    deadline_from: Optional[date] = None
    deadline_to: Optional[date] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
