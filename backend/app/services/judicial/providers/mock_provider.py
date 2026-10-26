"""
Mock Judicial Source Provider.

Provides high-fidelity, deterministic synthetic court cases from Bihar District Courts
and Patna High Court for testing, offline simulation, and benchmarking.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.schemas.judicial import JudicialCaseRecord, JudicialSearchQuery
from app.services.judicial.providers.base import (
    JudicialSourceProvider,
    JudicialInvalidQueryError,
)

# Seeded canonical cases representing real Bihar jurisdictional structures
SEED_MOCK_CASES: List[Dict[str, Any]] = [
    {
        "cnr_number": "BRPT01-001420-2021",
        "court_name": "Patna District & Sessions Court",
        "court_type": "DISTRICT_COURT",
        "district": "PATNA",
        "state": "Bihar",
        "case_type": "Title Suit",
        "case_number": "T.S./142/2021",
        "filing_year": 2021,
        "filing_date": datetime(2021, 4, 15, 10, 30, tzinfo=timezone.utc),
        "registration_date": datetime(2021, 4, 20, 11, 0, tzinfo=timezone.utc),
        "case_status": "PENDING",
        "stage_of_case": "Hearing on Injunction Application",
        "petitioner_names": ["Ram Swaroop Yadav", "Manoj Kumar Yadav"],
        "respondent_names": ["Dinanath Prasad", "Laxmi Devi", "Suresh Prasad"],
        "advocate_petitioner": "Alok Kumar Sinha",
        "advocate_respondent": "Rakesh Ranjan",
        "acts_sections": ["Specific Relief Act Sec 34", "Order 39 Rules 1 & 2 CPC"],
        "property_schedule_raw": "Mauza: Bakhtiyarpur, Thana No: 214, Khata: 45, Khesra (Plot): 102, Area: 1 Acre 20 Decimals",
        "extracted_land_identifiers": {
            "district": "PATNA",
            "circle": "Bakhtiyarpur",
            "mauza": "Bakhtiyarpur",
            "thana_number": "214",
            "khata": "45",
            "khesra": "102",
            "area_decimals": 120.0,
        },
        "orders_summary": [
            {
                "order_date": "2021-05-10",
                "order_type": "Notice Issued",
                "summary": "Notice ordered to respondents on injunction petition.",
            },
            {
                "order_date": "2022-09-15",
                "order_type": "Interim Injunction",
                "summary": "Both parties directed to maintain status quo regarding alienation and possession till next date.",
            },
        ],
        "has_active_injunction": True,
        "risk_category": "TITLE_DISPUTE",
        "source_url": "https://services.ecourts.gov.in/ecourtindia_v6/?p=casestatus&cnr=BRPT010014202021",
        "source_provider": "MOCK_PROVIDER",
    },
    {
        "cnr_number": "BRHC01-008921-2022",
        "court_name": "High Court of Judicature at Patna",
        "court_type": "HIGH_COURT",
        "district": "PATNA",
        "state": "Bihar",
        "case_type": "CWJC",
        "case_number": "CWJC/8921/2022",
        "filing_year": 2022,
        "filing_date": datetime(2022, 6, 12, 14, 0, tzinfo=timezone.utc),
        "registration_date": datetime(2022, 6, 18, 10, 0, tzinfo=timezone.utc),
        "case_status": "PENDING",
        "stage_of_case": "For Admission",
        "petitioner_names": ["Sunil Kumar"],
        "respondent_names": ["The State of Bihar", "The Collector, Patna", "The Circle Officer, Phulwari"],
        "advocate_petitioner": "Vikas Kumar",
        "advocate_respondent": "Government Pleader 14",
        "acts_sections": ["Constitution of India Art 226", "Bihar Land Mutation Act 2011 Sec 9"],
        "property_schedule_raw": "Plot No 412, Khata No 88, Mauza Phulwarisharif, District Patna.",
        "extracted_land_identifiers": {
            "district": "PATNA",
            "circle": "Phulwarisharif",
            "mauza": "Phulwarisharif",
            "khata": "88",
            "khesra": "412",
        },
        "orders_summary": [
            {
                "order_date": "2022-07-20",
                "order_type": "Time Granted",
                "summary": "Four weeks time granted to State Counsel to file counter affidavit.",
            }
        ],
        "has_active_injunction": False,
        "risk_category": "WRIT_LITIGATION",
        "source_url": "https://patnahighcourt.gov.in/case-status/cwjc-8921-2022",
        "source_provider": "MOCK_PROVIDER",
    },
    {
        "cnr_number": "BRSR01-000880-2020",
        "court_name": "Saran at Chapra Civil Court",
        "court_type": "DISTRICT_COURT",
        "district": "SARAN",
        "state": "Bihar",
        "case_type": "Title Partition Suit",
        "case_number": "T.P.S./88/2020",
        "filing_year": 2020,
        "filing_date": datetime(2020, 2, 10, 11, 0, tzinfo=timezone.utc),
        "registration_date": datetime(2020, 2, 15, 12, 0, tzinfo=timezone.utc),
        "case_status": "DISPOSED",
        "stage_of_case": "Disposed by Compromise",
        "petitioner_names": ["Kameshwar Singh"],
        "respondent_names": ["Tribhuwan Singh", "Sharda Devi"],
        "advocate_petitioner": "B. N. Pandey",
        "advocate_respondent": "A. K. Tiwary",
        "acts_sections": ["Partition Act 1893", "Civil Procedure Code Sec 54"],
        "property_schedule_raw": "Ancestral land under Khata 112, Khesra 450, Mauza Manjhi, Saran.",
        "extracted_land_identifiers": {
            "district": "SARAN",
            "circle": "Manjhi",
            "mauza": "Manjhi",
            "khata": "112",
            "khesra": "450",
        },
        "orders_summary": [
            {
                "order_date": "2021-11-25",
                "order_type": "Final Decree",
                "summary": "Suit disposed of in terms of joint compromise petition filed by parties.",
            }
        ],
        "has_active_injunction": False,
        "risk_category": "PARTITION_PROCEEDING",
        "source_url": "https://services.ecourts.gov.in/ecourtindia_v6/?p=casestatus&cnr=BRSR010008802020",
        "source_provider": "MOCK_PROVIDER",
    },
    {
        # Common party name with NO parcel identifiers in docket
        # Designed specifically to test unverified candidate behavior
        "cnr_number": "BRPT01-009999-2023",
        "court_name": "Patna District Court",
        "court_type": "DISTRICT_COURT",
        "district": "PATNA",
        "state": "Bihar",
        "case_type": "Money Suit",
        "case_number": "M.S./99/2023",
        "filing_year": 2023,
        "filing_date": datetime(2023, 1, 10, 10, 0, tzinfo=timezone.utc),
        "registration_date": datetime(2023, 1, 15, 11, 0, tzinfo=timezone.utc),
        "case_status": "PENDING",
        "stage_of_case": "Summons",
        "petitioner_names": ["Ram Kumar"],
        "respondent_names": ["State of Bihar", "Dinanath Prasad"],
        "advocate_petitioner": "P. K. Verma",
        "advocate_respondent": None,
        "acts_sections": ["CPC Order 37"],
        "property_schedule_raw": None,
        "extracted_land_identifiers": {},
        "orders_summary": [],
        "has_active_injunction": False,
        "risk_category": "OTHER",
        "source_url": "https://services.ecourts.gov.in/ecourtindia_v6/?p=casestatus&cnr=BRPT010099992023",
        "source_provider": "MOCK_PROVIDER",
    },
]


class MockJudicialProvider(JudicialSourceProvider):
    """
    Mock implementation of JudicialSourceProvider.
    Maintains an in-memory registry initialized from SEED_MOCK_CASES,
    and supports dynamic injection and configurable fault injection.
    """

    def __init__(self, failure_mode: Optional[str] = None):
        self._cases: Dict[str, JudicialCaseRecord] = {}
        self.failure_mode = failure_mode  # e.g., 'UNAVAILABLE', 'TIMEOUT', 'RATE_LIMIT'
        self._load_seed_cases()

    @property
    def provider_id(self) -> str:
        return "MOCK_JUDICIAL_PROVIDER"

    def _load_seed_cases(self) -> None:
        for c in SEED_MOCK_CASES:
            rec = JudicialCaseRecord(**c)
            self._cases[rec.cnr_number] = rec

    def register_case(self, case: JudicialCaseRecord) -> None:
        """Inject or override a case in the mock registry."""
        self._cases[case.cnr_number] = case

    async def search_cases(
        self,
        query: JudicialSearchQuery,
        timeout_seconds: float = 10.0,
    ) -> List[JudicialCaseRecord]:
        if self.failure_mode == "UNAVAILABLE":
            from app.services.judicial.providers.base import JudicialSourceUnavailableError
            raise JudicialSourceUnavailableError("Mock portal is currently offline for maintenance.")
        if self.failure_mode == "RATE_LIMIT":
            from app.services.judicial.providers.base import JudicialRateLimitError
            raise JudicialRateLimitError("Mock provider simulated rate limit reached (HTTP 429).")

        results: List[JudicialCaseRecord] = []

        # Exact CNR lookup
        if query.cnr_number:
            normalized_cnr = query.cnr_number.strip().upper().replace(" ", "")
            for cnr, case in self._cases.items():
                if cnr.replace("-", "").upper() == normalized_cnr.replace("-", ""):
                    return [case]
            return []

        # Multi-attribute search
        for case in self._cases.values():
            # District filter
            if query.district and case.district.upper() != query.district.strip().upper():
                continue

            # Filing year filter
            if query.filing_year and case.filing_year != query.filing_year:
                continue

            # Case type filter
            if query.case_type and query.case_type.upper() not in case.case_type.upper():
                continue

            # Party name search (substring or token match in petitioners or respondents)
            if query.party_name:
                q_name = query.party_name.strip().upper()
                # Remove common honorifics
                q_clean = re.sub(r"\b(SRI|SHRI|LATE|SMT|DEVI|YADAV|SINGH|PRASAD|KUMAR)\b", "", q_name).strip()
                tokens = [t for t in q_name.split() if len(t) > 2]

                found_party = False
                all_parties = [p.upper() for p in (case.petitioner_names + case.respondent_names)]
                for party in all_parties:
                    if q_name in party:
                        found_party = True
                        break
                    if any(tok in party for tok in tokens):
                        found_party = True
                        break

                if not found_party:
                    continue

            results.append(case)

        return results

    async def get_case_by_cnr(
        self,
        cnr_number: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[JudicialCaseRecord]:
        if self.failure_mode == "UNAVAILABLE":
            from app.services.judicial.providers.base import JudicialSourceUnavailableError
            raise JudicialSourceUnavailableError("Mock portal is currently offline.")

        norm = cnr_number.strip().upper().replace("-", "")
        for cnr, case in self._cases.items():
            if cnr.replace("-", "").upper() == norm:
                return case
        return None

    async def health_check(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": "HEALTHY" if not self.failure_mode else f"FAULT_{self.failure_mode}",
            "registered_cases_count": len(self._cases),
            "supported_jurisdictions": ["PATNA_HIGH_COURT", "BIHAR_DISTRICT_COURTS"],
        }
