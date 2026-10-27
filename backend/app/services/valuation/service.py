"""
Bihar MVR Circle Rate and Stamp Duty Valuation Service.

Coordinates schedule lookup, deterministic valuation computation, statutory charge assessment,
discrepancy evaluation, persistence, and coverage auditing while enforcing multi-tenant isolation.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.base import utc_now
from app.models.case import Case
from app.models.parcel import Parcel
from app.models.user import User, UserRole
from app.models.audit import AuditLog
from app.models.valuation import (
    MVRSchedule,
    PropertyValuation,
    PropertyCategory,
    RoadCategory,
    JurisdictionType,
    ScheduleVerificationStatus,
    DiscrepancyStatus,
    AUTHORIZED_OFFICIAL_VALUATION_PROVIDERS,
    SYNTHETIC_MOCK_VALUATION_PROVIDERS,
    ValuationSourceProviderType,
)
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError, ForbiddenError
from app.schemas.valuation import (
    MVRScheduleRecord,
    MVRScheduleCreateRequest,
    MVRScheduleSearchQuery,
    ValuationCalculationRequest,
    ValuationCalculationResponse,
    DiscrepancyAnalysisResult,
    MVRDistrictCoverageSummary,
    MVRScheduleVerifyRequest,
    STATUTORY_VALUATION_DISCLAIMER,
)
from app.services.valuation.providers import (
    get_valuation_provider,
    OperatorImportValuationProvider,
    SEED_MVR_SCHEDULES,
    MVRRateNotFoundError,
    InvalidJurisdictionError,
)
from app.services.valuation.valuation_engine import ValuationEngine
from app.services.valuation.stamp_duty_engine import StampDutyEngine
from app.services.valuation.discrepancy_analyzer import ValuationDiscrepancyAnalyzer

logger = logging.getLogger("bhumisetu.valuation.service")


class ValuationService:
    """
    Main business orchestration service for MVR Circle Rates and Stamp Duty Valuation.
    """

    def __init__(self):
        self.val_engine = ValuationEngine()
        self.stamp_engine = StampDutyEngine()
        self.discrepancy_analyzer = ValuationDiscrepancyAnalyzer()

    def _verify_tenant_access(self, entity_org_id: Optional[uuid.UUID], current_user: User, entity_name: str) -> None:
        """Enforces tenant isolation across organization boundaries."""
        if entity_org_id and current_user.org_id and entity_org_id != current_user.org_id:
            raise CrossTenantAccessError(f"Cross-tenant access prohibited for {entity_name}.")

    def _sync_seed_schedules_to_db_if_empty(self, db: Session) -> None:
        """Ensures canonical Bihar pilot schedules exist in the database."""
        count = db.query(MVRSchedule).count()
        if count == 0:
            for s in SEED_MVR_SCHEDULES:
                sched = MVRSchedule(
                    schedule_id=uuid.uuid4(),
                    schedule_code=s["schedule_code"],
                    district=s["district"],
                    registration_office=s["registration_office"],
                    anchal_circle=s["anchal_circle"],
                    mauza=s["mauza"],
                    thana_number=s.get("thana_number"),
                    jurisdiction_type=s["jurisdiction_type"],
                    property_category=s["property_category"],
                    land_classification=s["land_classification"],
                    road_category=s["road_category"],
                    rate_per_decimal=s["rate_per_decimal"],
                    rate_per_sqft=s.get("rate_per_sqft"),
                    rate_per_katha=s.get("rate_per_katha"),
                    unit_basis=s["unit_basis"],
                    effective_from=s["effective_from"],
                    effective_to=s.get("effective_to"),
                    version_number=s["version_number"],
                    is_active=s["is_active"],
                    verification_status=s["verification_status"],
                    source_gazette_reference=s.get("source_gazette_reference"),
                    source_url=s.get("source_url"),
                    source_provider=s["source_provider"],
                    raw_source_payload={k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in s.items()},
                )
                db.add(sched)
            db.commit()

    async def calculate_and_assess_property(
        self,
        db: Session,
        request: ValuationCalculationRequest,
        current_user: User,
        provider_type: Optional[str] = None,
    ) -> ValuationCalculationResponse:
        """
        Calculates government valuation, stamp duty, registration fees, and discrepancy analysis.
        """
        self._sync_seed_schedules_to_db_if_empty(db)

        # 1. Enforce Tenant Isolation for Case/Parcel if provided
        target_case: Optional[Case] = None
        if request.case_id:
            target_case = db.query(Case).filter(Case.case_id == request.case_id).first()
            if not target_case:
                raise EntityNotFoundError("Case", request.case_id)
            self._verify_tenant_access(target_case.org_id, current_user, "Case")

        target_parcel: Optional[Parcel] = None
        if request.parcel_id:
            target_parcel = db.query(Parcel).filter(Parcel.parcel_id == request.parcel_id).first()
            if not target_parcel:
                raise EntityNotFoundError("Parcel", request.parcel_id)
            self._verify_tenant_access(target_parcel.org_id, current_user, "Parcel")

            # Check jurisdiction match between request and parcel
            if target_parcel.district:
                p_dist = target_parcel.district.strip().upper()
                r_dist = request.district.strip().upper()
                if p_dist != r_dist:
                    raise InvalidJurisdictionError(
                        f"Valuation request district '{request.district}' does not match parcel district '{target_parcel.district}'."
                    )
            if target_parcel.circle:
                p_circle = target_parcel.circle.strip().upper()
                r_circle = request.anchal_circle.strip().upper()
                if p_circle != r_circle:
                    raise InvalidJurisdictionError(
                        f"Valuation request circle '{request.anchal_circle}' does not match parcel circle '{target_parcel.circle}'."
                    )
            if target_parcel.mauza:
                p_mauza = target_parcel.mauza.strip().upper()
                r_mauza = request.mauza.strip().upper()
                if p_mauza != r_mauza:
                    raise InvalidJurisdictionError(
                        f"Valuation request mauza '{request.mauza}' does not match parcel mauza '{target_parcel.mauza}'."
                    )

        # 2. Lookup matching MVR Schedule
        req_district = request.district.strip().upper()
        req_anchal = request.anchal_circle.strip().upper()
        req_mauza = request.mauza.strip().upper()
        req_cat = request.property_category.strip().upper()
        req_road = request.road_category.strip().upper()
        val_date = request.valuation_date or utc_now()

        # Query active, non-superseded schedules matching jurisdiction and effective dates
        schedule_query = db.query(MVRSchedule).filter(
            MVRSchedule.district == req_district,
            MVRSchedule.is_active == True,
            MVRSchedule.verification_status != ScheduleVerificationStatus.SUPERSEDED,
            MVRSchedule.effective_from <= val_date,
            sa.or_(MVRSchedule.effective_to.is_(None), MVRSchedule.effective_to >= val_date),
        )

        db_schedules = schedule_query.all()
        exact_match: Optional[MVRSchedule] = None
        fallback_match: Optional[MVRSchedule] = None

        # Prefer exact match with road category, prioritizing VERIFIED_OFFICIAL
        for s in db_schedules:
            if s.anchal_circle.upper() == req_anchal and s.mauza.upper() == req_mauza:
                if s.property_category.upper() == req_cat:
                    if s.road_category.upper() == req_road:
                        if not exact_match or (
                            s.verification_status == ScheduleVerificationStatus.VERIFIED_OFFICIAL
                            and exact_match.verification_status != ScheduleVerificationStatus.VERIFIED_OFFICIAL
                        ):
                            exact_match = s
                    else:
                        if not fallback_match or (
                            s.verification_status == ScheduleVerificationStatus.VERIFIED_OFFICIAL
                            and fallback_match.verification_status != ScheduleVerificationStatus.VERIFIED_OFFICIAL
                        ):
                            fallback_match = s

        matched_schedule = exact_match or fallback_match

        # If not found in DB, try provider
        if not matched_schedule:
            provider = get_valuation_provider(provider_type)
            p_schedules = await provider.search_schedules(
                MVRScheduleSearchQuery(
                    district=request.district,
                    anchal_circle=request.anchal_circle,
                    mauza=request.mauza,
                    property_category=request.property_category,
                    road_category=request.road_category,
                )
            )
            if p_schedules:
                p_rec = p_schedules[0]
                source_prov = (p_rec.source_provider or "MOCK_PROVIDER").upper()
                is_mock_provider = (
                    source_prov in SYNTHETIC_MOCK_VALUATION_PROVIDERS
                    or "MOCK" in source_prov
                    or "SYNTH" in source_prov
                    or "mock" in p_rec.schedule_code.lower()
                    or "synth" in p_rec.schedule_code.lower()
                )
                ver_status = (
                    ScheduleVerificationStatus.PROVISIONAL
                    if is_mock_provider
                    else p_rec.verification_status
                )
                matched_schedule = MVRSchedule(
                    schedule_id=uuid.uuid4(),
                    schedule_code=p_rec.schedule_code,
                    district=p_rec.district,
                    registration_office=p_rec.registration_office,
                    anchal_circle=p_rec.anchal_circle,
                    mauza=p_rec.mauza,
                    thana_number=p_rec.thana_number,
                    jurisdiction_type=p_rec.jurisdiction_type,
                    property_category=p_rec.property_category,
                    land_classification=p_rec.land_classification,
                    road_category=p_rec.road_category,
                    rate_per_decimal=p_rec.rate_per_decimal,
                    rate_per_sqft=p_rec.rate_per_sqft,
                    rate_per_katha=p_rec.rate_per_katha,
                    unit_basis=p_rec.unit_basis,
                    effective_from=p_rec.effective_from,
                    version_number=p_rec.version_number,
                    is_active=True,
                    verification_status=ver_status,
                    source_gazette_reference=p_rec.source_gazette_reference,
                    source_url=p_rec.source_url,
                    source_provider=p_rec.source_provider,
                    raw_source_payload=p_rec.model_dump(mode="json"),
                )
                db.add(matched_schedule)
                db.flush()

        if not matched_schedule:
            raise MVRRateNotFoundError(
                f"No verified MVR circle rate found for District '{request.district}', "
                f"Anchal '{request.anchal_circle}', Mauza '{request.mauza}', Category '{request.property_category}'."
            )

        # 3. Compute Valuation
        sched_record = MVRScheduleRecord.model_validate(matched_schedule)
        val_result = self.val_engine.calculate_valuation(request, sched_record)

        # 4. Compute Statutory Charges (Stamp Duty & Registration Fee)
        jurisdiction = request.jurisdiction_type or matched_schedule.jurisdiction_type
        charge_result = self.stamp_engine.calculate_charges(
            government_valuation=val_result["total_government_valuation"],
            declared_consideration=request.declared_consideration,
            buyer_category=request.buyer_category,
            jurisdiction_type=jurisdiction,
        )

        # 5. Analyze Discrepancy
        discrepancy_result = self.discrepancy_analyzer.analyze_discrepancy(
            government_valuation=val_result["total_government_valuation"],
            declared_consideration=request.declared_consideration,
            assessment_base=charge_result["assessment_base"],
        )

        # 6. Idempotently Persist PropertyValuation
        db_val = PropertyValuation(
            valuation_id=uuid.uuid4(),
            org_id=current_user.org_id,
            case_id=request.case_id,
            parcel_id=request.parcel_id,
            schedule_id=matched_schedule.schedule_id,
            valuation_date=request.valuation_date or utc_now(),
            total_area_decimal=val_result["total_area_decimal"],
            input_area_value=val_result["input_area_value"],
            input_area_unit=val_result["input_area_unit"],
            unit_circle_rate=val_result["applied_unit_rate"],
            calculated_land_value=val_result["calculated_land_value"],
            built_up_area_sqft=val_result["built_up_area_sqft"],
            construction_rate_sqft=val_result["construction_rate_sqft"],
            calculated_structure_value=val_result["calculated_structure_value"],
            total_government_valuation=val_result["total_government_valuation"],
            declared_transaction_consideration=charge_result["declared_consideration"],
            assessment_base=charge_result["assessment_base"],
            buyer_category=charge_result["buyer_category"],
            stamp_duty_rate_percent=charge_result["stamp_duty_rate_percent"],
            stamp_duty_amount=charge_result["stamp_duty_amount"],
            registration_fee_rate_percent=charge_result["registration_fee_rate_percent"],
            registration_fee_amount=charge_result["registration_fee_amount"],
            municipal_surcharge_percent=charge_result["municipal_surcharge_percent"],
            municipal_surcharge_amount=charge_result["municipal_surcharge_amount"],
            total_statutory_charges=charge_result["total_statutory_charges"],
            concession_applied=charge_result["concession_applied"],
            discrepancy_status=discrepancy_result["discrepancy_status"],
            discrepancy_amount=discrepancy_result["variance_amount"],
            discrepancy_percentage=discrepancy_result["variance_percentage"],
            discrepancy_explanation=discrepancy_result.get("explanation") or "No discrepancy detected.",
            rule_version=self.val_engine.RULE_VERSION,
            created_by_user_id=current_user.user_id,
        )
        db.add(db_val)
        db.commit()
        db.refresh(db_val)

        return ValuationCalculationResponse(
            valuation_id=str(db_val.valuation_id),
            schedule_code=matched_schedule.schedule_code,
            district=matched_schedule.district,
            anchal_circle=matched_schedule.anchal_circle,
            mauza=matched_schedule.mauza,
            property_category=matched_schedule.property_category,
            road_category=matched_schedule.road_category,
            jurisdiction_type=matched_schedule.jurisdiction_type,
            total_area_decimal=float(db_val.total_area_decimal),
            input_area_value=float(db_val.input_area_value),
            input_area_unit=db_val.input_area_unit,
            applied_unit_rate=float(db_val.unit_circle_rate),
            rate_basis=val_result["rate_basis"],
            calculated_land_value=float(db_val.calculated_land_value),
            calculated_structure_value=float(db_val.calculated_structure_value),
            total_government_valuation=float(db_val.total_government_valuation),
            declared_consideration=float(db_val.declared_transaction_consideration) if db_val.declared_transaction_consideration is not None else None,
            assessment_base=float(db_val.assessment_base),
            stamp_duty_rate_percent=float(db_val.stamp_duty_rate_percent),
            stamp_duty_amount=float(db_val.stamp_duty_amount),
            registration_fee_rate_percent=float(db_val.registration_fee_rate_percent),
            registration_fee_amount=float(db_val.registration_fee_amount),
            municipal_surcharge_percent=float(db_val.municipal_surcharge_percent),
            municipal_surcharge_amount=float(db_val.municipal_surcharge_amount),
            total_statutory_charges=float(db_val.total_statutory_charges),
            concession_applied=db_val.concession_applied,
            discrepancy_status=db_val.discrepancy_status,
            discrepancy_amount=float(db_val.discrepancy_amount),
            discrepancy_percentage=float(db_val.discrepancy_percentage),
            discrepancy_explanation=db_val.discrepancy_explanation,
            verification_status=matched_schedule.verification_status,
            rule_version=db_val.rule_version,
            valuation_date=db_val.valuation_date,
            disclaimer=STATUTORY_VALUATION_DISCLAIMER,
        )

    def import_schedule(
        self,
        db: Session,
        request: MVRScheduleCreateRequest,
        current_user: User,
    ) -> MVRScheduleRecord:
        """
        Ingests an official circle rate schedule via operator workflow.
        Newly imported schedules enter as PROVISIONAL pending supervisor verification.
        """
        import_provider = OperatorImportValuationProvider()
        record = import_provider.normalize_and_register(request, operator_user_id=str(current_user.user_id))

        # Check existing by schedule_code
        db_sched = db.query(MVRSchedule).filter(MVRSchedule.schedule_code == record.schedule_code).first()
        prev_state = None
        if not db_sched:
            db_sched = MVRSchedule(
                schedule_id=uuid.uuid4(),
                org_id=current_user.org_id,
                schedule_code=record.schedule_code,
                district=record.district,
                registration_office=record.registration_office,
                anchal_circle=record.anchal_circle,
                mauza=record.mauza,
                thana_number=record.thana_number,
                jurisdiction_type=record.jurisdiction_type,
                property_category=record.property_category,
                land_classification=record.land_classification,
                road_category=record.road_category,
                rate_per_decimal=record.rate_per_decimal,
                rate_per_sqft=record.rate_per_sqft,
                rate_per_katha=record.rate_per_katha,
                unit_basis=record.unit_basis,
                effective_from=record.effective_from,
                version_number=record.version_number,
                is_active=True,
                verification_status=ScheduleVerificationStatus.PROVISIONAL,
                source_gazette_reference=record.source_gazette_reference,
                source_url=record.source_url,
                source_provider="OPERATOR_ASSISTED_IMPORT",
                raw_source_payload=request.model_dump(mode="json"),
            )
            db.add(db_sched)
        else:
            self._verify_tenant_access(db_sched.org_id, current_user, "MVRSchedule")
            prev_state = {
                "rate_per_decimal": float(db_sched.rate_per_decimal),
                "verification_status": db_sched.verification_status,
                "version_number": db_sched.version_number,
            }
            db_sched.rate_per_decimal = record.rate_per_decimal
            db_sched.rate_per_sqft = record.rate_per_sqft
            db_sched.rate_per_katha = record.rate_per_katha
            db_sched.effective_from = record.effective_from
            db_sched.source_gazette_reference = record.source_gazette_reference
            db_sched.verification_status = ScheduleVerificationStatus.PROVISIONAL
            db_sched.version_number += 1

        db.flush()

        audit = AuditLog(
            log_id=uuid.uuid4(),
            org_id=current_user.org_id or db_sched.org_id or uuid.UUID("00000000-0000-0000-0000-000000000001"),
            actor_party_id=current_user.user_id,
            action="MVR_SCHEDULE_IMPORTED",
            entity_name="MVRSchedule",
            entity_id=db_sched.schedule_id,
            previous_state=prev_state,
            new_state={
                "schedule_code": db_sched.schedule_code,
                "verification_status": db_sched.verification_status,
                "district": db_sched.district,
                "mauza": db_sched.mauza,
                "rate_per_decimal": float(db_sched.rate_per_decimal),
                "source_gazette_reference": db_sched.source_gazette_reference,
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(db_sched)
        return MVRScheduleRecord.model_validate(db_sched)

    def verify_schedule(
        self,
        db: Session,
        schedule_id: uuid.UUID,
        verify_request: MVRScheduleVerifyRequest,
        current_user: User,
    ) -> MVRScheduleRecord:
        """
        Updates verification status of an MVR schedule.
        Restricted to ADMIN or SUPERVISOR roles.
        Enforces that synthetic/mock schedules cannot be verified as official.
        """
        if current_user.role not in (UserRole.ADMIN, UserRole.SUPERVISOR):
            audit = AuditLog(
                log_id=uuid.uuid4(),
                org_id=current_user.org_id or uuid.UUID("00000000-0000-0000-0000-000000000001"),
                actor_party_id=current_user.user_id,
                action="MVR_SCHEDULE_VERIFY_UNAUTHORIZED",
                entity_name="MVRSchedule",
                entity_id=schedule_id,
                previous_state=None,
                new_state={
                    "attempted_status": verify_request.verification_status,
                    "user_role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
                },
            )
            db.add(audit)
            db.commit()
            raise ForbiddenError("Only ADMIN or SUPERVISOR can verify MVR schedules.")

        sched = db.query(MVRSchedule).filter(MVRSchedule.schedule_id == schedule_id).first()
        if not sched:
            raise EntityNotFoundError("MVRSchedule", schedule_id)
        self._verify_tenant_access(sched.org_id, current_user, "MVRSchedule")

        prev_status = sched.verification_status
        new_status = verify_request.verification_status.strip().upper()

        if new_status == ScheduleVerificationStatus.VERIFIED_OFFICIAL:
            source_prov = (sched.source_provider or "").upper()
            is_mock_or_synth = (
                source_prov in SYNTHETIC_MOCK_VALUATION_PROVIDERS
                or "MOCK" in source_prov
                or "SYNTH" in source_prov
                or "mock" in sched.schedule_code.lower()
                or "synth" in sched.schedule_code.lower()
            )
            if is_mock_or_synth:
                raise ValueError(
                    f"Schedule '{sched.schedule_code}' is derived from '{sched.source_provider}' and cannot become VERIFIED_OFFICIAL."
                )

            if source_prov not in AUTHORIZED_OFFICIAL_VALUATION_PROVIDERS:
                raise ValueError(
                    f"Schedule source provider '{sched.source_provider}' is not an authorized official government registry."
                )

            gaz_ref = (sched.source_gazette_reference or "").strip()
            if not gaz_ref or len(gaz_ref) < 5 or gaz_ref.upper() in ("NONE", "N/A", "NULL", "TEST"):
                raise ValueError(
                    f"Schedule '{sched.schedule_code}' cannot be verified as official without a valid gazette notification reference."
                )

        sched.verification_status = new_status
        if new_status == ScheduleVerificationStatus.SUPERSEDED:
            sched.is_active = False
        elif new_status == ScheduleVerificationStatus.UNVERIFIED:
            sched.is_active = False

        audit = AuditLog(
            log_id=uuid.uuid4(),
            org_id=current_user.org_id or sched.org_id or uuid.UUID("00000000-0000-0000-0000-000000000001"),
            actor_party_id=current_user.user_id,
            action=f"MVR_SCHEDULE_{new_status}",
            entity_name="MVRSchedule",
            entity_id=sched.schedule_id,
            previous_state={"verification_status": prev_status, "is_active": sched.is_active},
            new_state={
                "verification_status": new_status,
                "is_active": sched.is_active,
                "notes": verify_request.verification_notes,
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(sched)
        return MVRScheduleRecord.model_validate(sched)

    def get_district_coverage(self, db: Session, current_user: User) -> List[MVRDistrictCoverageSummary]:
        """
        Aggregates coverage metrics across Bihar districts.
        """
        self._sync_seed_schedules_to_db_if_empty(db)
        schedules = db.query(MVRSchedule).filter(MVRSchedule.is_active == True).all()

        districts: Dict[str, Dict[str, Any]] = {}
        for s in schedules:
            d = s.district
            if d not in districts:
                districts[d] = {
                    "district": d,
                    "total_schedules": 0,
                    "verified_schedules": 0,
                    "unverified_schedules": 0,
                    "anchals": set(),
                    "categories": set(),
                    "freshness": s.effective_from,
                }
            districts[d]["total_schedules"] += 1
            if s.verification_status == ScheduleVerificationStatus.VERIFIED_OFFICIAL:
                districts[d]["verified_schedules"] += 1
            else:
                districts[d]["unverified_schedules"] += 1
            districts[d]["anchals"].add(s.anchal_circle)
            districts[d]["categories"].add(s.property_category)

        output: List[MVRDistrictCoverageSummary] = []
        for d_info in districts.values():
            status = "VERIFIED_ACTIVE" if d_info["verified_schedules"] > 0 else "PARTIAL_COVERAGE"
            output.append(
                MVRDistrictCoverageSummary(
                    district=d_info["district"],
                    total_schedules=d_info["total_schedules"],
                    verified_schedules=d_info["verified_schedules"],
                    unverified_schedules=d_info["unverified_schedules"],
                    anchals_covered=sorted(list(d_info["anchals"])),
                    property_categories_available=sorted(list(d_info["categories"])),
                    coverage_status=status,
                    data_freshness_timestamp=d_info["freshness"],
                )
            )
        return output

    def search_schedules(
        self,
        db: Session,
        query: MVRScheduleSearchQuery,
        current_user: User,
    ) -> List[MVRScheduleRecord]:
        """
        Searches available MVR schedules.
        """
        self._sync_seed_schedules_to_db_if_empty(db)
        q = db.query(MVRSchedule).filter(MVRSchedule.is_active == True)
        if query.district:
            q = q.filter(MVRSchedule.district == query.district.strip().upper())
        if query.anchal_circle:
            q = q.filter(MVRSchedule.anchal_circle.ilike(f"%{query.anchal_circle.strip()}%"))
        if query.mauza:
            q = q.filter(MVRSchedule.mauza.ilike(f"%{query.mauza.strip()}%"))
        if query.property_category:
            q = q.filter(MVRSchedule.property_category == query.property_category.strip().upper())
        if query.road_category:
            q = q.filter(MVRSchedule.road_category == query.road_category.strip().upper())

        return [MVRScheduleRecord.model_validate(s) for s in q.all()]
