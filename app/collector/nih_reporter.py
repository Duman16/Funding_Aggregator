from typing import List, Dict, Any

import structlog

from app.collector.base import BaseCollector

logger = structlog.get_logger()

NIH_API_URL = "https://api.reporter.nih.gov/v2/projects/search"


class NIHReporterCollector(BaseCollector):
    """
    Collector for NIH RePORTER public API.
    Docs: https://api.reporter.nih.gov/
    No auth required.
    """

    source_name = "nih_reporter"
    PAGE_SIZE = 50

    async def collect(self) -> List[Dict[str, Any]]:
        all_grants: List[Dict[str, Any]] = []

        for offset in range(0, 100, self.PAGE_SIZE):
            page = await self._fetch_page(offset)
            all_grants.extend(page)
            if len(page) < self.PAGE_SIZE:
                break

        logger.info("nih.collected", total=len(all_grants))
        return all_grants

    async def _fetch_page(self, offset: int = 0) -> List[Dict[str, Any]]:
        payload = {
            "criteria": {
                "fiscal_years": [2024, 2025],
                "include_active_projects": True,
            },
            "offset": offset,
            "limit": self.PAGE_SIZE,
            "sort_field": "project_start_date",
            "sort_order": "desc",
        }
        try:
            response = await self._post(NIH_API_URL, json=payload)
            data = response.json()
            results = data.get("results", [])
            return [self._normalize(r) for r in results]
        except Exception as e:
            logger.error("nih.page_error", offset=offset, error=str(e))
            return []

    def _normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        core = raw.get("project_title", "")
        appl_id = str(raw.get("appl_id", ""))
        return {
            "external_id": appl_id,
            "source": self.source_name,
            "title": core or "NIH Research Project",
            "description": raw.get("abstract_text", ""),
            "opportunity_number": raw.get("full_project_num", ""),
            "agency_name": raw.get("agency_ic_fundings", [{}])[0].get("name", "NIH") if raw.get("agency_ic_fundings") else "NIH",
            "agency_code": "NIH",
            "posted_date": raw.get("project_start_date", None),
            "deadline": raw.get("project_end_date", None),
            "amount_min": None,
            "amount_max": raw.get("award_amount", None),
            "url": f"https://reporter.nih.gov/project-details/{appl_id}",
            "status": "open",
            "eligibility": "Research institutions, Universities",
            "raw_data": None,
        }
