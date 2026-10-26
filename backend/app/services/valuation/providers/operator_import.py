"""
Operator-Assisted MVR Schedule Ingestion Provider.

Ingests and normalizes official District Collectorate circle rate notifications,
gazettes, and verified schedule extracts when automated web access is impeded by CAPTCHA.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.models.valuation import (
    AreaUnit,
    PropertyCategory,
    RoadCategory,
    ScheduleVerificationStatus,
)
from app.schemas.valuation import MVRScheduleRecord, MVRScheduleCreateRequest
from app.services.valuation.providers.base import (
    ValuationSourceProvider,
    InvalidJurisdictionError,
)
from app.services.valuation.unit_converter import convert_area


def generate_schedule_code(
    district: str,
    anchal: str,
    mauza: str,
    prop_cat: str,
    road_cat: str,
    version: int = 1,
) -> str:
    """Generates a canonical, deterministic schedule code."""
    d_clean = re.sub(r"[^A-Z0-9]", "", district.upper())[:3]
    a_clean = re.sub(r"[^A-Z0-9]", "", anchal.upper())[:3]
    m_clean = re.sub(r"[^A-Z0-9]", "", mauza.upper())[:3]
    p_clean = re.sub(r"[^A-Z0-9]", "", prop_cat.upper())[:3]
    r_clean = re.sub(r"[^A-Z0-9]", "", road_cat.upper())[:3]
    v_tag = f"V{version}" if version > 1 else ""
    return f"MVR-BR-{d_clean}-{a_clean}-{m_clean}-{p_clean}-{r_clean}{v_tag}"


class OperatorImportValuationProvider(ValuationSourceProvider):
    """
    Provider for operator-assisted verified MVR schedule imports.
    """

    def __init__(self):
        self._schedules: Dict[str, MVRScheduleRecord] = {}

    @property
    def provider_id(self) -> str:
        return "OPERATOR_ASSISTED_IMPORT"

    def normalize_and_register(
        self,
        request: MVRScheduleCreateRequest,
        operator_user_id: Optional[str] = None,
        version: int = 1,
    ) -> MVRScheduleRecord:
        """
        Validates, normalizes, and registers an official circle rate schedule.
        Calculates sqft and katha rates automatically if omitted.
        """
        district = request.district.strip().upper()
        anchal = request.anchal_circle.strip().title()
        mauza = request.mauza.strip().title()

        if not district or not anchal or not mauza:
            raise InvalidJurisdictionError("District, Anchal, and Mauza must be non-empty.")

        if request.rate_per_decimal <= 0:
            raise ValueError(f"Rate per decimal must be positive, got {request.rate_per_decimal}")

        # Compute derived rates if not supplied:
        # 1 Decimal = 435.60 SqFt; 1 Katha = 3.125 Decimals
        rate_sqft = request.rate_per_sqft
        if rate_sqft is None or rate_sqft <= 0:
            rate_sqft = round(request.rate_per_decimal / 435.60, 2)

        rate_katha = request.rate_per_katha
        if rate_katha is None or rate_katha <= 0:
            rate_katha = round(request.rate_per_decimal * 3.125, 2)

        schedule_code = request.schedule_code or generate_schedule_code(
            district=district,
            anchal=anchal,
            mauza=mauza,
            prop_cat=request.property_category,
            road_cat=request.road_category,
            version=version,
        )

        record = MVRScheduleRecord(
            schedule_id=str(uuid.uuid4()),
            schedule_code=schedule_code,
            district=district,
            registration_office=request.registration_office.strip(),
            anchal_circle=anchal,
            mauza=mauza,
            thana_number=request.thana_number.strip() if request.thana_number else None,
            jurisdiction_type=request.jurisdiction_type,
            property_category=request.property_category,
            land_classification=request.land_classification,
            road_category=request.road_category,
            rate_per_decimal=request.rate_per_decimal,
            rate_per_sqft=rate_sqft,
            rate_per_katha=rate_katha,
            unit_basis=request.unit_basis,
            effective_from=request.effective_from or datetime.now(timezone.utc),
            version_number=version,
            is_active=True,
            verification_status=ScheduleVerificationStatus.VERIFIED_OFFICIAL,
            source_gazette_reference=request.source_gazette_reference,
            source_url=request.source_url,
            source_provider=self.provider_id,
        )

        self._schedules[record.schedule_code] = record
        return record

    async def search_schedules(
        self,
        query: Any,
        timeout_seconds: float = 10.0,
    ) -> List[MVRScheduleRecord]:
        return list(self._schedules.values())

    async def get_schedule_by_code(
        self,
        schedule_code: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[MVRScheduleRecord]:
        return self._schedules.get(schedule_code)

    async def get_district_coverage(self) -> List[Dict[str, Any]]:
        return []

    async def health_check(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": "HEALTHY",
            "imported_schedules_count": len(self._schedules),
        }
