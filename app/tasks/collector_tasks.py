import asyncio
import structlog
from app.tasks.celery_app import celery_app

logger = structlog.get_logger()


def _run_async(coro):
    """Helper to run async code from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def collect_grants_gov(self):
    """Celery task: collect grants from Grants.gov."""
    logger.info("task.collect_grants_gov.started")
    try:
        return _run_async(_collect_grants_gov_async())
    except Exception as exc:
        logger.error("task.collect_grants_gov.failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def collect_nih_reporter(self):
    """Celery task: collect grants from NIH RePORTER."""
    logger.info("task.collect_nih_reporter.started")
    try:
        return _run_async(_collect_nih_async())
    except Exception as exc:
        logger.error("task.collect_nih_reporter.failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def collect_usa_spending(self):
    """Celery task: collect grants from USASpending.gov."""
    logger.info("task.collect_usa_spending.started")
    try:
        return _run_async(_collect_usa_spending_async())
    except Exception as exc:
        logger.error("task.collect_usa_spending.failed", error=str(exc))
        raise self.retry(exc=exc)


async def _collect_grants_gov_async():
    from app.collector.grants_gov import GrantsGovCollector
    from app.processor.pipeline import run_pipeline
    from app.database import AsyncSessionLocal

    collector = GrantsGovCollector()
    result = await collector.run()

    if result["status"] == "success" and result["data"]:
        async with AsyncSessionLocal() as db:
            log = await run_pipeline(db, result["data"], "grants_gov")
            return {
                "source": "grants_gov",
                "collected": log.records_collected,
                "new": log.records_new,
                "updated": log.records_updated,
            }
    return {"source": "grants_gov", "status": result["status"]}


async def _collect_nih_async():
    from app.collector.nih_reporter import NIHReporterCollector
    from app.processor.pipeline import run_pipeline
    from app.database import AsyncSessionLocal

    collector = NIHReporterCollector()
    result = await collector.run()

    if result["status"] == "success" and result["data"]:
        async with AsyncSessionLocal() as db:
            log = await run_pipeline(db, result["data"], "nih_reporter")
            return {
                "source": "nih_reporter",
                "collected": log.records_collected,
                "new": log.records_new,
                "updated": log.records_updated,
            }
    return {"source": "nih_reporter", "status": result["status"]}


async def _collect_usa_spending_async():
    from app.collector.usa_spending import USASpendingCollector
    from app.processor.pipeline import run_pipeline
    from app.database import AsyncSessionLocal

    collector = USASpendingCollector()
    result = await collector.run()

    if result["status"] == "success" and result["data"]:
        async with AsyncSessionLocal() as db:
            log = await run_pipeline(db, result["data"], "usa_spending")
            return {
                "source": "usa_spending",
                "collected": log.records_collected,
                "new": log.records_new,
                "updated": log.records_updated,
            }
    return {"source": "usa_spending", "status": result["status"]}
