from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func

from app.database import get_db
from app.models.grant import Grant
from app.models.scrape_log import ScrapeLog

router = APIRouter(tags=["System"])


@router.get("/health", summary="Health check")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
    }


@router.get("/stats", summary="Database statistics")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_grants = (await db.execute(select(func.count()).select_from(Grant))).scalar_one()
    open_grants = (
        await db.execute(select(func.count()).select_from(Grant).where(Grant.status == "open"))
    ).scalar_one()
    sources = (
        await db.execute(
            select(Grant.source, func.count(Grant.id)).group_by(Grant.source)
        )
    ).all()
    last_scrape = (
        await db.execute(
            select(ScrapeLog).order_by(ScrapeLog.started_at.desc()).limit(1)
        )
    ).scalar_one_or_none()

    return {
        "total_grants": total_grants,
        "open_grants": open_grants,
        "sources": {s: c for s, c in sources},
        "last_scrape": {
            "source": last_scrape.source,
            "status": last_scrape.status,
            "records_new": last_scrape.records_new,
            "started_at": last_scrape.started_at,
        } if last_scrape else None,
    }
