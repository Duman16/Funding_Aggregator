import json
from typing import Any

import structlog

from app.collector.base import BaseCollector

logger = structlog.get_logger()

GRANTS_GOV_SEARCH_URL = "https://apply07.grants.gov/grantsws/rest/opportunities/search/"


class GrantsGovCollector(BaseCollector):
    """
    Collector for Grants.gov public REST API.
    Docs: https://www.grants.gov/web/grants/s2s/grantor/schemas/grants-funding-synopsis.html
    No API key required — completely open.
    """

    source_name = "grants_gov"
    PAGE_SIZE = 25

    async def collect(self) -> list[dict[str, Any]]:
        all_grants: list[dict[str, Any]] = []

        # Fetch multiple pages to get 100+ records
        for start_record in range(0, 100, self.PAGE_SIZE):
            page_grants = await self._fetch_page(start_record)
            all_grants.extend(page_grants)
            if not page_grants:
                break

        logger.info("grants_gov.collected", total=len(all_grants))
        return all_grants

    async def _fetch_page(self, start_record: int = 0) -> list[dict[str, Any]]:
        payload = {
            "startRecordNum": start_record,
            "rows": self.PAGE_SIZE,
            "oppStatuses": "forecasted|posted",
            "sortBy": "openDate|desc",
        }

        try:
            response = await self._post(
                GRANTS_GOV_SEARCH_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            data = response.json()
            opportunities = data.get("oppHits", [])
            return [self._normalize(opp) for opp in opportunities]
        except Exception as e:
            logger.error("grants_gov.page_error", start=start_record, error=str(e))
            return []

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize a single Grants.gov opportunity to our schema."""
        return {
            "external_id": str(raw.get("id", "")),
            "source": self.source_name,
            "title": raw.get("title", "Untitled Grant"),
            "description": raw.get("synopsis", raw.get("description", "")),
            "opportunity_number": raw.get("number", ""),
            "agency_name": raw.get("agencyName", ""),
            "agency_code": raw.get("agencyCode", ""),
            "posted_date": raw.get("openDate", None),
            "deadline": raw.get("closeDate", None),
            "amount_min": self._parse_amount(raw.get("awardFloor")),
            "amount_max": self._parse_amount(raw.get("awardCeiling")),
            "url": f"https://www.grants.gov/web/grants/view-opportunity.html?oppId={raw.get('id', '')}",
            "status": "open" if raw.get("oppStatus", "").lower() == "posted" else "forecasted",
            "eligibility": raw.get("eligibilities", ""),
            "raw_data": json.dumps(raw),
        }

    @staticmethod
    def _parse_amount(value) -> float | None:
        if value is None:
            return None
        try:
            cleaned = str(value).replace(",", "").strip()
            result = float(cleaned)
            return result if result > 0 else None
        except (ValueError, TypeError):
            return None
