from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.grant import Grant, GrantCategory
from app.models.scrape_log import ScrapeLog
from app.processor.cleaner import (
    clean_html,
    clean_title,
    extract_keywords,
    normalize_status,
    parse_amount,
    parse_date,
)

logger = structlog.get_logger()

# Auto-categorization rules: (keyword_in_title_or_desc -> category_slug)
CATEGORY_RULES = [
    (["health", "medical", "medicine", "clinical", "disease", "biomedical"], "health"),
    (["science", "research", "laboratory", "experiment", "stem"], "science"),
    (["technology", "tech", "software", "digital", "cyber", "ai", "data"], "technology"),
    (["education", "school", "university", "student", "learning", "academic"], "education"),
    (["environment", "climate", "energy", "renewable", "green", "ecology"], "environment"),
    (["community", "social", "nonprofit", "public", "welfare"], "social"),
    (["arts", "culture", "humanities", "music", "theater", "literature"], "arts"),
    (["agriculture", "food", "farm", "rural", "crop"], "agriculture"),
    (["defense", "security", "military", "homeland"], "defense"),
    (["international", "global", "foreign", "development"], "international"),
]


async def _get_or_create_category(db: AsyncSession, slug: str) -> Category | None:
    result = await db.execute(select(Category).where(Category.slug == slug))
    cat = result.scalar_one_or_none()
    if cat:
        return cat
    # Map slug to display name
    name_map = {
        "health": "Health & Medicine",
        "science": "Science & Research",
        "technology": "Technology",
        "education": "Education",
        "environment": "Environment & Energy",
        "social": "Social & Community",
        "arts": "Arts & Humanities",
        "agriculture": "Agriculture & Food",
        "defense": "Defense & Security",
        "international": "International",
    }
    cat = Category(slug=slug, name=name_map.get(slug, slug.title()))
    db.add(cat)
    await db.flush()
    return cat


def _infer_categories(title: str, description: str) -> list[str]:
    text = f"{title} {description}".lower()
    found = []
    for keywords, slug in CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            found.append(slug)
    return found[:3]  # cap at 3 categories per grant


async def process_grant(db: AsyncSession, raw: dict[str, Any]) -> tuple[str, Grant]:
    """
    Process a single raw grant dict: clean, normalize, upsert into DB.
    Returns ('created' | 'updated' | 'skipped', grant_object)
    """
    external_id = str(raw.get("external_id", "")).strip()
    source = raw.get("source", "unknown")

    if not external_id:
        return "skipped", None

    # Check for existing record
    result = await db.execute(
        select(Grant).where(and_(Grant.external_id == external_id, Grant.source == source))
    )
    grant = result.scalar_one_or_none()
    action = "updated" if grant else "created"

    # Clean & normalize
    title = clean_title(raw.get("title")) or "Untitled"
    description = clean_html(raw.get("description"))
    keywords = extract_keywords(f"{title} {description or ''}")

    if not grant:
        grant = Grant(external_id=external_id, source=source)
        db.add(grant)

    grant.title = title
    grant.description = description
    grant.opportunity_number = raw.get("opportunity_number")
    grant.agency_name = (raw.get("agency_name") or "")[:300] or None
    grant.agency_code = (raw.get("agency_code") or "")[:50] or None
    grant.posted_date = parse_date(raw.get("posted_date"))
    grant.deadline = parse_date(raw.get("deadline"))
    grant.amount_min = parse_amount(raw.get("amount_min"))
    grant.amount_max = parse_amount(raw.get("amount_max"))
    grant.url = (raw.get("url") or "")[:1000]
    grant.status = normalize_status(raw.get("status"))
    grant.eligibility = (raw.get("eligibility") or "")[:2000] or None
    grant.keywords = keywords
    grant.is_processed = True

    await db.flush()

    # Assign categories
    category_slugs = _infer_categories(title, description or "")
    for slug in category_slugs:
        cat = await _get_or_create_category(db, slug)
        if cat:
            existing = await db.execute(
                select(GrantCategory).where(
                    and_(
                        GrantCategory.grant_id == grant.id,
                        GrantCategory.category_id == cat.id,
                    )
                )
            )
            if not existing.scalar_one_or_none():
                db.add(GrantCategory(grant_id=grant.id, category_id=cat.id))

    return action, grant


async def run_pipeline(
    db: AsyncSession,
    raw_data: list[dict[str, Any]],
    source: str,
) -> ScrapeLog:
    """Run the full processing pipeline and return a ScrapeLog."""
    started_at = datetime.now(UTC)
    log = logger.bind(source=source)
    log.info("pipeline.started", total=len(raw_data))

    counts = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    for item in raw_data:
        try:
            action, _ = await process_grant(db, item)
            counts[action] = counts.get(action, 0) + 1
        except Exception as e:
            counts["errors"] += 1
            log.error("pipeline.item_error", error=str(e))

    await db.commit()

    scrape_log = ScrapeLog(
        source=source,
        status="success" if counts["errors"] == 0 else "partial",
        records_collected=len(raw_data),
        records_new=counts["created"],
        records_updated=counts["updated"],
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )
    db.add(scrape_log)
    await db.commit()

    log.info("pipeline.finished", **counts)
    return scrape_log
