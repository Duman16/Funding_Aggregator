import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String, Text, Date, DateTime, Boolean, Numeric,
    ForeignKey, Index, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Grant(Base):
    __tablename__ = "grants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opportunity_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Organization
    agency_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    agency_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Dates
    posted_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Funding
    amount_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    amount_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)

    # Meta
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    eligibility: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)

    # Processing
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Full-text search
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    # Relationships
    categories: Mapped[List["GrantCategory"]] = relationship(
        "GrantCategory", back_populates="grant", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("external_id", "source", name="uq_grant_external_source"),
        Index("ix_grant_deadline", "deadline"),
        Index("ix_grant_status", "status"),
        Index("ix_grant_source", "source"),
        Index("ix_grant_agency", "agency_name"),
        Index("ix_grant_search_vector", "search_vector", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Grant {self.title[:50]}>"


class GrantCategory(Base):
    __tablename__ = "grant_categories"

    grant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grants.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )

    grant: Mapped["Grant"] = relationship("Grant", back_populates="categories")
    category: Mapped["Category"] = relationship("Category", back_populates="grants")
