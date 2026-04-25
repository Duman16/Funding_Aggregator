"""
Collector for USASpending.gov public API.
Docs: https://api.usaspending.gov/
No API key required — fully open government data.
Collects federal grant awards (assistance listings).
"""

from typing import Any

import structlog

from app.collector.base import BaseCollector

logger = structlog.get_logger()

USA_SPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


class USASpendingCollector(BaseCollector):
    """
    Collector for USASpending.gov federal grant awards.
    Uses the /api/v2/search/spending_by_award/ endpoint.
    """

    source_name = "usa_spending"
    PAGE_SIZE = 50

    async def collect(self) -> list[dict[str, Any]]:
        all_grants: list[dict[str, Any]] = []

        for page in range(1, 4):  # 3 pages × 50 = 150 records max
            page_grants = await self._fetch_page(page)
            all_grants.extend(page_grants)
            if not page_grants:
                break

        logger.info("usa_spending.collected", total=len(all_grants))
        return all_grants

    async def _fetch_page(self, page: int = 1) -> list[dict[str, Any]]:
        payload = {
            "filters": {
                "award_type_codes": ["02", "03", "04", "05"],  # grants only
                "time_period": [{"start_date": "2024-01-01", "end_date": "2025-12-31"}],
            },
            "fields": [
                "Award ID",
                "Recipient Name",
                "Start Date",
                "End Date",
                "Award Amount",
                "Awarding Agency",
                "Awarding Sub Agency",
                "Award Type",
                "Description",
                "def_codes",
                "COVID-19 Obligations",
                "recipient_id",
                "prime_award_recipient_id",
            ],
            "page": page,
            "limit": self.PAGE_SIZE,
            "sort": "Award Amount",
            "order": "desc",
        }

        try:
            response = await self._post(
                USA_SPENDING_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            data = response.json()
            results = data.get("results", [])
            return [self._normalize(r) for r in results if r]
        except Exception as e:
            logger.error("usa_spending.page_error", page=page, error=str(e))
            return []

    def _normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize a USASpending award to our Grant schema."""
        award_id = str(raw.get("Award ID", "")).strip()
        amount = raw.get("Award Amount")

        return {
            "external_id": award_id or f"usa_{hash(str(raw))}",
            "source": self.source_name,
            "title": self._build_title(raw),
            "description": raw.get("Description") or "",
            "opportunity_number": award_id,
            "agency_name": raw.get("Awarding Agency", ""),
            "agency_code": self._shorten_agency(raw.get("Awarding Sub Agency", "")),
            "posted_date": raw.get("Start Date"),
            "deadline": raw.get("End Date"),
            "amount_min": None,
            "amount_max": float(amount) if amount else None,
            "url": (
                f"https://www.usaspending.gov/award/{award_id}/"
                if award_id
                else "https://www.usaspending.gov/"
            ),
            "status": "open",
            "eligibility": "Federal award recipients — see USASpending.gov for eligibility details",
        }

    @staticmethod
    def _build_title(raw: dict[str, Any]) -> str:
        """Build a meaningful title from available fields."""
        recipient = raw.get("Recipient Name", "")
        agency = raw.get("Awarding Sub Agency", raw.get("Awarding Agency", ""))
        award_type = raw.get("Award Type", "Grant")

        if recipient and agency:
            return f"{award_type}: {recipient} — {agency}"[:500]
        elif recipient:
            return f"Federal {award_type} — {recipient}"[:500]
        return f"Federal {award_type} Award"

    @staticmethod
    def _shorten_agency(name: str) -> str:
        if not name:
            return ""
        # Take first letters of capitalized words as code
        words = name.split()
        code = "".join(w[0] for w in words if w[0].isupper())
        return code[:50] or name[:50]
