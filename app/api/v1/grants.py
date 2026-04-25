from typing import Optional
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, cast, String
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.grant import Grant, GrantCategory
from app.models.category import Category
from app.schemas.grant import GrantOut, GrantListOut
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/grants", tags=["Grants"])

AVAILABLE_SOURCES = ["grants_gov", "nih_reporter", "usa_spending"]


def _build_query(
    search: Optional[str] = None,
    source: Optional[str] = None,
    status_filter: Optional[str] = None,
    agency_name: Optional[str] = None,
    category_slug: Optional[str] = None,
    deadline_from: Optional[date] = None,
    deadline_to: Optional[date] = None,
    amount_min: Optional[Decimal] = None,
    amount_max: Optional[Decimal] = None,
):
    """Build a filtered SQLAlchemy query for grants."""
    query = select(Grant).options(
        selectinload(Grant.categories).selectinload(GrantCategory.category)
    )

    conditions = []

    if search:
        ts_query = func.plainto_tsquery("english", search)
        ts_vector = func.to_tsvector(
            "english",
            func.coalesce(Grant.title, "")
            + " "
            + func.coalesce(Grant.description, "")
            + " "
            + func.coalesce(cast(Grant.agency_name, String), ""),
        )
        conditions.append(ts_vector.op("@@")(ts_query))

    if source:
        conditions.append(Grant.source == source)

    if status_filter:
        conditions.append(Grant.status == status_filter)

    if agency_name:
        conditions.append(Grant.agency_name.ilike(f"%{agency_name}%"))

    if deadline_from:
        conditions.append(Grant.deadline >= deadline_from)

    if deadline_to:
        conditions.append(Grant.deadline <= deadline_to)

    if amount_min is not None:
        conditions.append(
            or_(Grant.amount_max >= amount_min, Grant.amount_min >= amount_min)
        )

    if amount_max is not None:
        conditions.append(
            or_(Grant.amount_min <= amount_max, Grant.amount_max <= amount_max)
        )

    if category_slug:
        query = query.join(Grant.categories).join(GrantCategory.category)
        conditions.append(Category.slug == category_slug)

    if conditions:
        query = query.where(and_(*conditions))

    return query


@router.get("", response_model=GrantListOut, summary="List grants with filters")
async def list_grants(
    search: Optional[str] = Query(None, description="Full-text search query"),
    source: Optional[str] = Query(None, description="Data source (grants_gov, nih_reporter, usa_spending)"),
    status: Optional[str] = Query(None, description="Grant status (open, forecasted, closed)"),
    agency_name: Optional[str] = Query(None, description="Agency name (partial match)"),
    category_slug: Optional[str] = Query(None, description="Category slug"),
    deadline_from: Optional[date] = Query(None, description="Deadline from (YYYY-MM-DD)"),
    deadline_to: Optional[date] = Query(None, description="Deadline to (YYYY-MM-DD)"),
    amount_min: Optional[Decimal] = Query(None, description="Minimum grant amount"),
    amount_max: Optional[Decimal] = Query(None, description="Maximum grant amount"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    query = _build_query(
        search=search, source=source, status_filter=status,
        agency_name=agency_name, category_slug=category_slug,
        deadline_from=deadline_from, deadline_to=deadline_to,
        amount_min=amount_min, amount_max=amount_max,
    )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (page - 1) * per_page
    query = query.order_by(Grant.deadline.asc().nulls_last(), Grant.created_at.desc())
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    grants = result.scalars().all()

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return GrantListOut(
        items=grants,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{grant_id}", response_model=GrantOut, summary="Get grant by ID")
async def get_grant(
    grant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Grant)
        .options(selectinload(Grant.categories).selectinload(GrantCategory.category))
        .where(Grant.id == grant_id)
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")
    return grant


@router.post("/collect/{source}", summary="Trigger manual collection (admin)", status_code=202)
async def trigger_collection(
    source: str,
    current_user=Depends(get_current_user),
):
    """Trigger a manual data collection task. Requires authentication."""
    from app.tasks.collector_tasks import (
        collect_grants_gov,
        collect_nih_reporter,
        collect_usa_spending,
    )

    task_map = {
        "grants_gov": collect_grants_gov,
        "nih_reporter": collect_nih_reporter,
        "usa_spending": collect_usa_spending,
    }
    task = task_map.get(source)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown source. Available: {list(task_map.keys())}",
        )
    result = task.delay()
    return {"task_id": result.id, "status": "queued", "source": source}
