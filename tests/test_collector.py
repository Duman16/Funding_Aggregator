from app.collector.grants_gov import GrantsGovCollector
from app.collector.nih_reporter import NIHReporterCollector


class TestGrantsGovCollector:
    def setup_method(self):
        self.collector = GrantsGovCollector()

    def test_normalize_full(self):
        raw = {
            "id": "12345",
            "title": "Test Grant Opportunity",
            "synopsis": "Research funding for science",
            "number": "NSF-2024-001",
            "agencyName": "National Science Foundation",
            "agencyCode": "NSF",
            "openDate": "01/01/2025",
            "closeDate": "06/30/2025",
            "awardFloor": "50000",
            "awardCeiling": "500000",
            "oppStatus": "Posted",
        }
        result = self.collector._normalize(raw)
        assert result["external_id"] == "12345"
        assert result["source"] == "grants_gov"
        assert result["title"] == "Test Grant Opportunity"
        assert result["status"] == "open"
        assert result["amount_min"] == 50000.0
        assert result["amount_max"] == 500000.0
        assert "grants.gov" in result["url"]

    def test_normalize_missing_fields(self):
        raw = {"id": "999"}
        result = self.collector._normalize(raw)
        assert result["external_id"] == "999"
        assert result["title"] == "Untitled Grant"
        assert result["amount_min"] is None

    def test_parse_amount_valid(self):
        assert self.collector._parse_amount("100,000") == 100000.0
        assert self.collector._parse_amount(500000) == 500000.0
        assert self.collector._parse_amount("1,500,000.50") == 1500000.5

    def test_parse_amount_invalid(self):
        assert self.collector._parse_amount(None) is None
        assert self.collector._parse_amount("N/A") is None
        assert self.collector._parse_amount(0) is None

    def test_normalize_forecasted_status(self):
        raw = {"id": "1", "oppStatus": "Forecasted"}
        result = self.collector._normalize(raw)
        assert result["status"] == "forecasted"


class TestNIHCollector:
    def setup_method(self):
        self.collector = NIHReporterCollector()

    def test_normalize(self):
        raw = {
            "appl_id": 9999,
            "project_title": "NIH Research Project",
            "abstract_text": "This study examines...",
            "full_project_num": "R01CA123456",
            "award_amount": 250000,
            "project_start_date": "2024-06-01",
            "project_end_date": "2026-05-31",
        }
        result = self.collector._normalize(raw)
        assert result["external_id"] == "9999"
        assert result["source"] == "nih_reporter"
        assert result["amount_max"] == 250000
        assert "reporter.nih.gov" in result["url"]


class TestUSASpendingCollector:
    def setup_method(self):
        from app.collector.usa_spending import USASpendingCollector

        self.collector = USASpendingCollector()

    def test_normalize_full(self):
        raw = {
            "Award ID": "GRANT-2024-001",
            "Recipient Name": "State University",
            "Awarding Agency": "Department of Health",
            "Awarding Sub Agency": "National Institutes of Health",
            "Award Amount": 250000,
            "Start Date": "2024-01-15",
            "End Date": "2025-12-31",
            "Award Type": "Grant",
            "Description": "Research funding for biomedical studies",
        }
        result = self.collector._normalize(raw)
        assert result["external_id"] == "GRANT-2024-001"
        assert result["source"] == "usa_spending"
        assert "State University" in result["title"]
        assert result["amount_max"] == 250000.0
        assert "usaspending.gov" in result["url"]

    def test_normalize_missing_amount(self):
        raw = {"Award ID": "ABC123", "Award Type": "Grant"}
        result = self.collector._normalize(raw)
        assert result["amount_max"] is None
        assert result["external_id"] == "ABC123"

    def test_build_title_with_recipient_and_agency(self):
        raw = {
            "Award ID": "1",
            "Recipient Name": "MIT",
            "Awarding Agency": "NSF",
            "Awarding Sub Agency": "National Science Foundation",
            "Award Type": "Grant",
        }
        result = self.collector._normalize(raw)
        assert "MIT" in result["title"]

    def test_shorten_agency(self):
        assert self.collector._shorten_agency("National Science Foundation") == "NSF"
        assert self.collector._shorten_agency("") == ""

    def test_source_name(self):
        assert self.collector.source_name == "usa_spending"
