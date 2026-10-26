"""
Operator-Assisted Judicial Case Ingestion Provider.

Supports compliant ingestion of certified court dockets, certified judgments,
advocate briefs, or manual eCourts printouts when automated public portal access
is blocked by CAPTCHA or security controls.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.schemas.judicial import (
    JudicialCaseRecord,
    JudicialManualIngestRequest,
    JudicialSearchQuery,
)
from app.services.judicial.providers.base import (
    JudicialSourceProvider,
    JudicialInvalidQueryError,
)

# Regex to detect land schedule markers in raw Bihar court plaints / property schedules
KHATA_REGEX = re.compile(r"(?:खता|खाता|khata|khatiyan)\s*(?:no\.?|संख्या)?\s*[:\-]?\s*([0-9\/\-]+)", re.IGNORECASE)
KHESRA_REGEX = re.compile(r"(?:खेसरा|खेसरा\s*नं|khesra|plot|dag)\s*(?:no\.?|संख्या)?\s*[:\-]?\s*([0-9\/\-]+)", re.IGNORECASE)
MAUZA_REGEX = re.compile(r"(?:मौजा|ग्राम|mauza|mouza|village)\s*[:\-]?\s*([A-Za-z\u0900-\u097F\s]+?)(?:,|\.|\n|थाना|thana)", re.IGNORECASE)
THANA_REGEX = re.compile(r"(?:थाना\s*नं|thana\s*no\.?)\s*[:\-]?\s*([0-9]+)", re.IGNORECASE)
AREA_DECIMAL_REGEX = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:decimal|डिसमिल|डीसमिल)", re.IGNORECASE)
AREA_ACRE_REGEX = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:acre|एकड़)", re.IGNORECASE)


def parse_property_schedule(raw_schedule: Optional[str]) -> Dict[str, Any]:
    """
    Deterministically parses land identifiers from unstructured court property schedules.
    Preserves raw text while extracting recognized plot/khata/mauza values.
    """
    if not raw_schedule:
        return {}

    identifiers: Dict[str, Any] = {}

    khata_match = KHATA_REGEX.search(raw_schedule)
    if khata_match:
        identifiers["khata"] = khata_match.group(1).strip()

    khesra_match = KHESRA_REGEX.search(raw_schedule)
    if khesra_match:
        identifiers["khesra"] = khesra_match.group(1).strip()

    mauza_match = MAUZA_REGEX.search(raw_schedule)
    if mauza_match:
        identifiers["mauza"] = mauza_match.group(1).strip()

    thana_match = THANA_REGEX.search(raw_schedule)
    if thana_match:
        identifiers["thana_number"] = thana_match.group(1).strip()

    # Calculate area if present
    decimals = 0.0
    dec_match = AREA_DECIMAL_REGEX.search(raw_schedule)
    if dec_match:
        try:
            decimals += float(dec_match.group(1))
        except ValueError:
            pass

    acre_match = AREA_ACRE_REGEX.search(raw_schedule)
    if acre_match:
        try:
            decimals += float(acre_match.group(1)) * 100.0
        except ValueError:
            pass

    if decimals > 0:
        identifiers["area_decimals"] = decimals

    return identifiers


class OperatorImportProvider(JudicialSourceProvider):
    """
    Provider for operator-assisted manual ingestion of certified judicial records.
    """

    def __init__(self):
        self._imported_cases: Dict[str, JudicialCaseRecord] = {}

    @property
    def provider_id(self) -> str:
        return "OPERATOR_ASSISTED_IMPORT"

    def normalize_and_register(
        self,
        request: JudicialManualIngestRequest,
        evidence_id: Optional[str] = None,
    ) -> JudicialCaseRecord:
        """
        Validates, normalizes, and registers a manually uploaded judicial proceeding.
        """
        clean_cnr = request.cnr_number.strip().upper().replace(" ", "").replace("-", "")
        if len(clean_cnr) != 16:
            raise JudicialInvalidQueryError(
                f"Invalid CNR '{request.cnr_number}'. CNR must be exactly 16 alphanumeric characters."
            )

        # Merge extracted land identifiers with parsed property schedule
        parsed_identifiers = parse_property_schedule(request.property_schedule_raw)
        if request.extracted_land_identifiers:
            parsed_identifiers.update(request.extracted_land_identifiers)

        record = JudicialCaseRecord(
            cnr_number=request.cnr_number.strip().upper(),
            court_name=request.court_name.strip(),
            court_type=request.court_type,
            district=request.district.strip().upper(),
            state="Bihar",
            case_type=request.case_type.strip(),
            case_number=request.case_number.strip(),
            filing_year=request.filing_year,
            case_status=request.case_status,
            stage_of_case=request.stage_of_case,
            petitioner_names=[p.strip() for p in request.petitioner_names if p.strip()],
            respondent_names=[r.strip() for r in request.respondent_names if r.strip()],
            advocate_petitioner=request.advocate_petitioner.strip() if request.advocate_petitioner else None,
            advocate_respondent=request.advocate_respondent.strip() if request.advocate_respondent else None,
            property_schedule_raw=request.property_schedule_raw,
            extracted_land_identifiers=parsed_identifiers,
            orders_summary=request.orders_summary or [],
            has_active_injunction=request.has_active_injunction,
            risk_category=request.risk_category,
            source_url=request.source_url,
            source_provider=self.provider_id,
            retrieval_timestamp=datetime.now(timezone.utc),
            evidence_id=str(request.certified_document_id) if request.certified_document_id else evidence_id,
        )

        self._imported_cases[record.cnr_number] = record
        return record

    async def search_cases(
        self,
        query: JudicialSearchQuery,
        timeout_seconds: float = 10.0,
    ) -> List[JudicialCaseRecord]:
        results: List[JudicialCaseRecord] = []
        if query.cnr_number:
            norm = query.cnr_number.strip().upper().replace("-", "")
            for cnr, c in self._imported_cases.items():
                if cnr.replace("-", "").upper() == norm:
                    return [c]
            return []

        for c in self._imported_cases.values():
            if query.district and c.district.upper() != query.district.strip().upper():
                continue
            if query.filing_year and c.filing_year != query.filing_year:
                continue
            if query.party_name:
                q = query.party_name.strip().upper()
                parties = [p.upper() for p in (c.petitioner_names + c.respondent_names)]
                if not any(q in p for p in parties):
                    continue
            results.append(c)
        return results

    async def get_case_by_cnr(
        self,
        cnr_number: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[JudicialCaseRecord]:
        norm = cnr_number.strip().upper().replace("-", "")
        for cnr, c in self._imported_cases.items():
            if cnr.replace("-", "").upper() == norm:
                return c
        return None

    async def health_check(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": "HEALTHY",
            "imported_cases_count": len(self._imported_cases),
        }
