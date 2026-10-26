"""
Mock Valuation Source Provider.

Provides high-fidelity, deterministic canonical MVR circle rates for Bihar pilot
districts (Patna, Gaya, Saran) for testing, offline simulation, and benchmarking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.schemas.valuation import MVRScheduleRecord, MVRScheduleSearchQuery
from app.services.valuation.providers.base import (
    ValuationSourceProvider,
    ValuationSourceUnavailableError,
    ValuationRateLimitError,
)

# Seeded official-style MVR schedules based on Bihar District Collectorate publications
SEED_MVR_SCHEDULES: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # PATNA DISTRICT — DANAPUR ANCHAL — KOTWA MAUZA
    # -------------------------------------------------------------
    {
        "schedule_code": "MVR-BR-PAT-DAN-KOT-AGR-NH",
        "district": "PATNA",
        "registration_office": "Danapur Sub-Registry",
        "anchal_circle": "Danapur",
        "mauza": "Kotwa",
        "thana_number": "18",
        "jurisdiction_type": "RURAL",
        "property_category": "AGRICULTURAL",
        "land_classification": "DHANHAR_I",
        "road_category": "MAIN_ROAD_NH_SH",
        "rate_per_decimal": 85000.0,
        "rate_per_sqft": 195.13,
        "rate_per_katha": 265625.0,
        "unit_basis": "DECIMAL",
        "effective_from": datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        "effective_to": None,
        "version_number": 1,
        "is_active": True,
        "verification_status": "VERIFIED_OFFICIAL",
        "source_gazette_reference": "Patna District Gazette Notification No. 412/Reg-2025",
        "source_url": "http://registration.bihar.gov.in/mvr/patna/danapur-kotwa",
        "source_provider": "MOCK_PROVIDER",
    },
    {
        "schedule_code": "MVR-BR-PAT-DAN-KOT-AGR-RUR",
        "district": "PATNA",
        "registration_office": "Danapur Sub-Registry",
        "anchal_circle": "Danapur",
        "mauza": "Kotwa",
        "thana_number": "18",
        "jurisdiction_type": "RURAL",
        "property_category": "AGRICULTURAL",
        "land_classification": "DHANHAR_I",
        "road_category": "RURAL_ROAD_OR_NO_ROAD",
        "rate_per_decimal": 45000.0,
        "rate_per_sqft": 103.31,
        "rate_per_katha": 140625.0,
        "unit_basis": "DECIMAL",
        "effective_from": datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        "effective_to": None,
        "version_number": 1,
        "is_active": True,
        "verification_status": "VERIFIED_OFFICIAL",
        "source_gazette_reference": "Patna District Gazette Notification No. 412/Reg-2025",
        "source_url": "http://registration.bihar.gov.in/mvr/patna/danapur-kotwa",
        "source_provider": "MOCK_PROVIDER",
    },
    {
        "schedule_code": "MVR-BR-PAT-DAN-KOT-RES-PWD",
        "district": "PATNA",
        "registration_office": "Danapur Sub-Registry",
        "anchal_circle": "Danapur",
        "mauza": "Kotwa",
        "thana_number": "18",
        "jurisdiction_type": "RURAL",
        "property_category": "RESIDENTIAL",
        "land_classification": "AWASIYA",
        "road_category": "PWD_ROAD",
        "rate_per_decimal": 120000.0,
        "rate_per_sqft": 275.48,
        "rate_per_katha": 375000.0,
        "unit_basis": "DECIMAL",
        "effective_from": datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        "effective_to": None,
        "version_number": 1,
        "is_active": True,
        "verification_status": "VERIFIED_OFFICIAL",
        "source_gazette_reference": "Patna District Gazette Notification No. 412/Reg-2025",
        "source_url": "http://registration.bihar.gov.in/mvr/patna/danapur-kotwa",
        "source_provider": "MOCK_PROVIDER",
    },
    {
        "schedule_code": "MVR-BR-PAT-DAN-KOT-COM-NH",
        "district": "PATNA",
        "registration_office": "Danapur Sub-Registry",
        "anchal_circle": "Danapur",
        "mauza": "Kotwa",
        "thana_number": "18",
        "jurisdiction_type": "RURAL",
        "property_category": "COMMERCIAL",
        "land_classification": "VYAVSAYIK",
        "road_category": "MAIN_ROAD_NH_SH",
        "rate_per_decimal": 250000.0,
        "rate_per_sqft": 573.92,
        "rate_per_katha": 781250.0,
        "unit_basis": "DECIMAL",
        "effective_from": datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        "effective_to": None,
        "version_number": 1,
        "is_active": True,
        "verification_status": "VERIFIED_OFFICIAL",
        "source_gazette_reference": "Patna District Gazette Notification No. 412/Reg-2025",
        "source_url": "http://registration.bihar.gov.in/mvr/patna/danapur-kotwa",
        "source_provider": "MOCK_PROVIDER",
    },

    # -------------------------------------------------------------
    # PATNA DISTRICT — PATNA SADAR (URBAN CORPORATION - PMC)
    # -------------------------------------------------------------
    {
        "schedule_code": "MVR-BR-PAT-SAD-KAN-RES-PMC",
        "district": "PATNA",
        "registration_office": "Patna Sadar Registry",
        "anchal_circle": "Patna Sadar",
        "mauza": "Kankarbagh",
        "thana_number": "20",
        "jurisdiction_type": "URBAN_CORPORATION",
        "property_category": "RESIDENTIAL",
        "land_classification": "AWASIYA",
        "road_category": "BRANCH_ROAD_MUNICIPAL",
        "rate_per_decimal": 650000.0,
        "rate_per_sqft": 1492.20,
        "rate_per_katha": 2031250.0,
        "unit_basis": "DECIMAL",
        "effective_from": datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        "effective_to": None,
        "version_number": 1,
        "is_active": True,
        "verification_status": "VERIFIED_OFFICIAL",
        "source_gazette_reference": "Patna Municipal Circle Rate Schedule 2025-26",
        "source_url": "http://registration.bihar.gov.in/mvr/patna/kankarbagh",
        "source_provider": "MOCK_PROVIDER",
    },
    {
        "schedule_code": "MVR-BR-PAT-SAD-KAN-COM-PMC",
        "district": "PATNA",
        "registration_office": "Patna Sadar Registry",
        "anchal_circle": "Patna Sadar",
        "mauza": "Kankarbagh",
        "thana_number": "20",
        "jurisdiction_type": "URBAN_CORPORATION",
        "property_category": "COMMERCIAL",
        "land_classification": "VYAVSAYIK",
        "road_category": "MAIN_ROAD_NH_SH",
        "rate_per_decimal": 1200000.0,
        "rate_per_sqft": 2754.82,
        "rate_per_katha": 3750000.0,
        "unit_basis": "DECIMAL",
        "effective_from": datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        "effective_to": None,
        "version_number": 1,
        "is_active": True,
        "verification_status": "VERIFIED_OFFICIAL",
        "source_gazette_reference": "Patna Municipal Circle Rate Schedule 2025-26",
        "source_url": "http://registration.bihar.gov.in/mvr/patna/kankarbagh",
        "source_provider": "MOCK_PROVIDER",
    },

    # -------------------------------------------------------------
    # PATNA DISTRICT — BAKHTIYARPUR ANCHAL (RURAL)
    # -------------------------------------------------------------
    {
        "schedule_code": "MVR-BR-PAT-BAK-BAK-AGR",
        "district": "PATNA",
        "registration_office": "Barh Sub-Registry",
        "anchal_circle": "Bakhtiyarpur",
        "mauza": "Bakhtiyarpur",
        "thana_number": "214",
        "jurisdiction_type": "RURAL",
        "property_category": "AGRICULTURAL",
        "land_classification": "DHANHAR_I",
        "road_category": "RURAL_ROAD_OR_NO_ROAD",
        "rate_per_decimal": 30000.0,
        "rate_per_sqft": 68.87,
        "rate_per_katha": 93750.0,
        "unit_basis": "DECIMAL",
        "effective_from": datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        "effective_to": None,
        "version_number": 1,
        "is_active": True,
        "verification_status": "VERIFIED_OFFICIAL",
        "source_gazette_reference": "Barh Sub-Registry Notification 2025",
        "source_url": "http://registration.bihar.gov.in/mvr/patna/bakhtiyarpur",
        "source_provider": "MOCK_PROVIDER",
    },

    # -------------------------------------------------------------
    # GAYA DISTRICT — BODH GAYA ANCHAL
    # -------------------------------------------------------------
    {
        "schedule_code": "MVR-BR-GAY-BOD-BOD-COM",
        "district": "GAYA",
        "registration_office": "Bodh Gaya Sub-Registry",
        "anchal_circle": "Bodh Gaya",
        "mauza": "Bodh Gaya",
        "thana_number": "54",
        "jurisdiction_type": "URBAN_MUNICIPAL",
        "property_category": "COMMERCIAL",
        "land_classification": "VYAVSAYIK",
        "road_category": "MAIN_ROAD_NH_SH",
        "rate_per_decimal": 400000.0,
        "rate_per_sqft": 918.27,
        "rate_per_katha": 1250000.0,
        "unit_basis": "DECIMAL",
        "effective_from": datetime(2025, 4, 1, 0, 0, tzinfo=timezone.utc),
        "effective_to": None,
        "version_number": 1,
        "is_active": True,
        "verification_status": "VERIFIED_OFFICIAL",
        "source_gazette_reference": "Gaya Collectorate Notification 102/2025",
        "source_url": "http://registration.bihar.gov.in/mvr/gaya/bodhgaya",
        "source_provider": "MOCK_PROVIDER",
    },
]


class MockValuationProvider(ValuationSourceProvider):
    """
    Mock implementation of ValuationSourceProvider.
    Maintains an in-memory registry of official Bihar MVR schedules.
    """

    def __init__(self, failure_mode: Optional[str] = None):
        self._schedules: Dict[str, MVRScheduleRecord] = {}
        self.failure_mode = failure_mode  # e.g., 'UNAVAILABLE', 'RATE_LIMIT'
        self._load_seed_schedules()

    @property
    def provider_id(self) -> str:
        return "MOCK_MVR_PROVIDER"

    def _load_seed_schedules(self) -> None:
        for s in SEED_MVR_SCHEDULES:
            rec = MVRScheduleRecord(schedule_id=s["schedule_code"], **s)
            self._schedules[rec.schedule_code] = rec

    def register_schedule(self, schedule: MVRScheduleRecord) -> None:
        """Inject or override an MVR schedule record in the mock registry."""
        self._schedules[schedule.schedule_code] = schedule

    async def search_schedules(
        self,
        query: MVRScheduleSearchQuery,
        timeout_seconds: float = 10.0,
    ) -> List[MVRScheduleRecord]:
        if self.failure_mode == "UNAVAILABLE":
            raise ValuationSourceUnavailableError("Mock registration portal is offline.")
        if self.failure_mode == "RATE_LIMIT":
            raise ValuationRateLimitError("Simulated rate limit exceeded (HTTP 429).")

        results: List[MVRScheduleRecord] = []
        for s in self._schedules.values():
            if not s.is_active:
                continue

            if query.district and s.district.upper() != query.district.strip().upper():
                continue

            if query.anchal_circle and query.anchal_circle.strip().upper() not in s.anchal_circle.upper():
                continue

            if query.mauza and query.mauza.strip().upper() not in s.mauza.upper():
                continue

            if query.property_category and s.property_category.upper() != query.property_category.strip().upper():
                continue

            if query.road_category and s.road_category.upper() != query.road_category.strip().upper():
                continue

            if query.effective_date:
                # Must be >= effective_from and (effective_to is None or <= effective_to)
                if s.effective_from > query.effective_date:
                    continue
                if s.effective_to and s.effective_to < query.effective_date:
                    continue

            results.append(s)

        return results

    async def get_schedule_by_code(
        self,
        schedule_code: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[MVRScheduleRecord]:
        if self.failure_mode == "UNAVAILABLE":
            raise ValuationSourceUnavailableError("Mock registration portal is offline.")
        return self._schedules.get(schedule_code)

    async def get_district_coverage(self) -> List[Dict[str, Any]]:
        districts: Dict[str, Dict[str, Any]] = {}
        for s in self._schedules.values():
            d = s.district
            if d not in districts:
                districts[d] = {
                    "district": d,
                    "total_schedules": 0,
                    "verified_schedules": 0,
                    "unverified_schedules": 0,
                    "anchals_covered": set(),
                    "property_categories_available": set(),
                    "coverage_status": "VERIFIED_ACTIVE",
                    "data_freshness_timestamp": s.effective_from,
                }
            districts[d]["total_schedules"] += 1
            if s.verification_status == "VERIFIED_OFFICIAL":
                districts[d]["verified_schedules"] += 1
            else:
                districts[d]["unverified_schedules"] += 1
            districts[d]["anchals_covered"].add(s.anchal_circle)
            districts[d]["property_categories_available"].add(s.property_category)

        output: List[Dict[str, Any]] = []
        for d_info in districts.values():
            output.append({
                "district": d_info["district"],
                "total_schedules": d_info["total_schedules"],
                "verified_schedules": d_info["verified_schedules"],
                "unverified_schedules": d_info["unverified_schedules"],
                "anchals_covered": sorted(list(d_info["anchals_covered"])),
                "property_categories_available": sorted(list(d_info["property_categories_available"])),
                "coverage_status": d_info["coverage_status"],
                "data_freshness_timestamp": d_info["data_freshness_timestamp"],
            })
        return output

    async def health_check(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": "HEALTHY" if not self.failure_mode else f"FAULT_{self.failure_mode}",
            "registered_schedules_count": len(self._schedules),
        }
