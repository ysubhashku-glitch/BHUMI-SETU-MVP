"""
Mock Mutation Source Adapter for Testing and Offline Environments.

Provides realistic synthetic Bihar pilot mutation records (Danapur, Patna Sadar, Gaya)
covering standard approvals, adverse rejection orders (dispute, area deficit),
and in-progress procedural hearings with complete lifecycle provenance.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional

from app.services.mutation.adapters.base import (
    MutationSourceAdapter,
    AdapterHealthStatus,
    MutationInvalidQueryError,
)

# Realistic pilot records for Bihar anchals
PILOT_MUTATION_CASES = [
    {
        "case_number": "MUT-2024-DAN-00104",
        "filing_year": 2024,
        "district": "Patna",
        "circle": "Danapur",
        "mauza": "Mustafapur",
        "mutation_type": "SALE_DEED",
        "khata_number": "45",
        "khesra_number": "128",
        "jamabandi_number": "JB-1044",
        "deed_number": "DEED-2024-PAT-8891",
        "deed_date": "2024-02-10",
        "deed_registered_office": "Sub-Registrar Danapur",
        "applicant_name": "Ramesh Kumar Sharma",
        "buyer_names": ["Ramesh Kumar Sharma"],
        "seller_names": ["Birendra Prasad Singh"],
        "filing_date": "2024-02-20",
        "disposal_date": "2024-04-15",
        "reported_status": "APPROVED",
        "normalized_status": "APPROVED",
        "raw_source_status": "स्वीकृत (Approved - Shuddhi Patra Issued)",
        "source_portal": "biharbhumi.bihar.gov.in",
        "source_authority": "Circle Officer, Danapur",
        "notes": "Mutation approved upon positive Karamchari report and non-receipt of objections under Form-IX.",
        "events": [
            {
                "event_type": "FILING_SUBMITTED",
                "reported_timestamp": "2024-02-20T10:30:00Z",
                "action_taken": "Online mutation application submitted via Bihar Bhumi portal.",
                "source_document_reference": "PETITION-DAN-2024-00104.pdf",
            },
            {
                "event_type": "REVENUE_OFFICER_SCRUTINY",
                "reported_timestamp": "2024-02-28T14:15:00Z",
                "action_taken": "Forwarded by Circle Officer to Halka Karamchari for field inquiry and Jamabandi verification.",
                "source_document_reference": "FORWARDING-MEMO-2024-0228",
            },
            {
                "event_type": "NOTICE_FORM_IX_ISSUED",
                "reported_timestamp": "2024-03-05T11:00:00Z",
                "action_taken": "General and special notice issued under Form-IX inviting public objections within 14 days.",
                "source_document_reference": "FORM_IX_NOTICE_104.pdf",
            },
            {
                "event_type": "FIELD_INQUIRY_REPORT_SUBMITTED",
                "reported_timestamp": "2024-03-24T16:00:00Z",
                "action_taken": "Halka Karamchari reported applicant in peaceful physical possession; Circle Inspector confirmed recommendation.",
                "source_document_reference": "CI_REPORT_DAN_104.pdf",
            },
            {
                "event_type": "FINAL_ORDER_PASSED",
                "reported_timestamp": "2024-04-15T15:30:00Z",
                "action_taken": "Circle Officer Danapur sanctioned mutation order in favor of buyer.",
                "source_document_reference": "ORDER_SHEET_DAN_104.pdf",
            },
            {
                "event_type": "SHUDDHI_PATRA_ISSUED",
                "reported_timestamp": "2024-04-18T10:00:00Z",
                "action_taken": "Correction slip (Shuddhi Patra) issued. Register-II updated with new Jamabandi entry.",
                "source_document_reference": "SHUDDHI_PATRA_104.pdf",
            },
        ],
    },
    {
        "case_number": "MUT-2024-DAN-00215",
        "filing_year": 2024,
        "district": "Patna",
        "circle": "Danapur",
        "mauza": "Mustafapur",
        "mutation_type": "SALE_DEED",
        "khata_number": "45",
        "khesra_number": "130",
        "jamabandi_number": "JB-1044",
        "deed_number": "DEED-2024-PAT-9012",
        "deed_date": "2024-03-01",
        "deed_registered_office": "Sub-Registrar Danapur",
        "applicant_name": "Suresh Prasad Singh",
        "buyer_names": ["Suresh Prasad Singh"],
        "seller_names": ["Birendra Prasad Singh"],
        "filing_date": "2024-03-12",
        "disposal_date": "2024-05-20",
        "reported_status": "REJECTED",
        "normalized_status": "REJECTED",
        "raw_source_status": "अस्वीकृत (Rejected - Disputed Title / Injunction)",
        "rejection_reason_code": "LAND_DISPUTED",
        "rejection_reason_details": "Objection filed with certified copy of Civil Court injunction in Title Suit No. 142/2023.",
        "source_portal": "biharbhumi.bihar.gov.in",
        "source_authority": "Circle Officer, Danapur",
        "notes": "Mutation rejected due to pending civil court title dispute and injunction order.",
        "events": [
            {
                "event_type": "FILING_SUBMITTED",
                "reported_timestamp": "2024-03-12T11:00:00Z",
                "action_taken": "Application submitted.",
                "source_document_reference": "PETITION-DAN-2024-00215.pdf",
            },
            {
                "event_type": "NOTICE_FORM_IX_ISSUED",
                "reported_timestamp": "2024-03-20T12:00:00Z",
                "action_taken": "Form-IX public notice issued.",
                "source_document_reference": "NOTICE_DAN_215.pdf",
            },
            {
                "event_type": "PUBLIC_OBJECTION_FILED",
                "reported_timestamp": "2024-04-02T14:30:00Z",
                "action_taken": "Objection petition received from co-sharers alleging pending partition and title injunction.",
                "source_document_reference": "OBJECTION_PETITION_215.pdf",
            },
            {
                "event_type": "HEARING_CONDUCTED",
                "reported_timestamp": "2024-04-25T11:30:00Z",
                "action_taken": "Parties heard before Circle Officer; stay order produced.",
                "source_document_reference": "HEARING_PROCEEDING_215.pdf",
            },
            {
                "event_type": "REJECTION_ORDER_PASSED",
                "reported_timestamp": "2024-05-20T16:00:00Z",
                "action_taken": "Petition rejected by Circle Officer under Bihar Mutation Act due to disputed title and injunction.",
                "source_document_reference": "REJECTION_ORDER_DAN_215.pdf",
            },
        ],
    },
    {
        "case_number": "MUT-2024-PAT-00450",
        "filing_year": 2024,
        "district": "Patna",
        "circle": "Patna Sadar",
        "mauza": "Sheikhpura",
        "mutation_type": "SALE_DEED",
        "khata_number": "112",
        "khesra_number": "540",
        "jamabandi_number": "JB-8821",
        "deed_number": "DEED-2024-SAD-3310",
        "deed_date": "2024-05-10",
        "deed_registered_office": "District Sub-Registrar Patna",
        "applicant_name": "Anita Devi",
        "buyer_names": ["Anita Devi"],
        "seller_names": ["Manoj Kumar"],
        "filing_date": "2024-05-18",
        "disposal_date": "2024-07-02",
        "reported_status": "REJECTED",
        "normalized_status": "REJECTED",
        "raw_source_status": "अस्वीकृत (Rejected - Vendor Area Deficit)",
        "rejection_reason_code": "AREA_DEFICIT",
        "rejection_reason_details": "Vendor holds 10 decimals in Jamabandi but deed conveys 15 decimals. Excess area unavailable for mutation.",
        "source_portal": "biharbhumi.bihar.gov.in",
        "source_authority": "Circle Officer, Patna Sadar",
        "notes": "Mutation rejected due to vendor area deficit in current Register-II record.",
        "events": [
            {
                "event_type": "FILING_SUBMITTED",
                "reported_timestamp": "2024-05-18T10:00:00Z",
                "action_taken": "Mutation petition filed.",
            },
            {
                "event_type": "FIELD_INQUIRY_REPORT_SUBMITTED",
                "reported_timestamp": "2024-06-15T15:00:00Z",
                "action_taken": "Karamchari reported that vendor Manoj Kumar previously sold 10 decimals; remaining area in Jamabandi is nil.",
            },
            {
                "event_type": "REJECTION_ORDER_PASSED",
                "reported_timestamp": "2024-07-02T14:00:00Z",
                "action_taken": "Rejected by CO Patna Sadar under Section 6 of Bihar Land Mutation Act for lack of vendor subsisting area.",
            },
        ],
    },
    {
        "case_number": "MUT-2024-GAYA-00812",
        "filing_year": 2024,
        "district": "Gaya",
        "circle": "Bodh Gaya",
        "mauza": "Bakrour",
        "mutation_type": "INHERITANCE_WARISAN",
        "khata_number": "89",
        "khesra_number": "310",
        "jamabandi_number": "JB-4520",
        "applicant_name": "Arun Kumar Yadav",
        "buyer_names": ["Arun Kumar Yadav", "Sunil Yadav"],
        "seller_names": ["Late Ramdhani Yadav"],
        "filing_date": "2024-06-01",
        "reported_status": "NOTICE_ISSUED",
        "normalized_status": "NOTICE_ISSUED",
        "raw_source_status": "नोटिस जारी (Form-IX Notice Issued - Objections Invited)",
        "source_portal": "biharbhumi.bihar.gov.in",
        "source_authority": "Circle Officer, Bodh Gaya",
        "notes": "Inheritance mutation proceeding pending expiry of public objection period.",
        "events": [
            {
                "event_type": "FILING_SUBMITTED",
                "reported_timestamp": "2024-06-01T09:30:00Z",
                "action_taken": "Warisan mutation petition filed with family tree genealogy affidavit.",
            },
            {
                "event_type": "NOTICE_FORM_IX_ISSUED",
                "reported_timestamp": "2024-06-12T11:00:00Z",
                "action_taken": "Form-IX notice issued to co-heirs and general public.",
            },
        ],
    },
]


class MockMutationAdapter(MutationSourceAdapter):
    """
    Mock source adapter returning authentic Bihar pilot mutation cases
    for testing, CI test runs, and offline development.
    """

    def __init__(self, cases: Optional[List[Dict[str, Any]]] = None):
        self._cases = cases if cases is not None else list(PILOT_MUTATION_CASES)

    @property
    def adapter_name(self) -> str:
        return "MOCK_ADAPTER"

    @property
    def health_status(self) -> AdapterHealthStatus:
        return AdapterHealthStatus.AVAILABLE

    async def search_cases(
        self,
        district: str,
        circle: str,
        mauza: Optional[str] = None,
        khata_number: Optional[str] = None,
        khesra_number: Optional[str] = None,
        case_number: Optional[str] = None,
        deed_number: Optional[str] = None,
        applicant_name: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> List[Dict[str, Any]]:
        results = []
        for c in self._cases:
            if district and c["district"].lower() != district.lower():
                continue
            if circle and c["circle"].lower() != circle.lower():
                continue
            if mauza and c["mauza"].lower() != mauza.lower():
                continue
            if case_number and case_number.lower() not in c["case_number"].lower():
                continue
            if khata_number and c.get("khata_number") != khata_number:
                continue
            if khesra_number and c.get("khesra_number") != khesra_number:
                continue
            if deed_number and c.get("deed_number") != deed_number:
                continue
            if applicant_name and applicant_name.lower() not in c.get("applicant_name", "").lower():
                continue
            results.append(c)
        return results

    async def get_case_detail(
        self,
        case_number: str,
        district: str,
        circle: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        for c in self._cases:
            if c["case_number"].lower() == case_number.lower():
                return c
        return None

    async def get_case_events(
        self,
        case_number: str,
        district: str,
        circle: str,
        timeout_seconds: float = 10.0,
    ) -> List[Dict[str, Any]]:
        detail = await self.get_case_detail(case_number, district, circle)
        if not detail:
            return []
        return detail.get("events", [])

    async def health_check(self) -> Dict[str, Any]:
        return {
            "adapter": self.adapter_name,
            "status": "UP",
            "available_cases_count": len(self._cases),
            "environment": "SYNTHETIC_PILOT_MOCK",
        }
