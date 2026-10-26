"""
Judicial Risk Intelligence Service.

Coordinates court case retrieval, normalization, persistence, deterministic entity resolution,
and operator review lifecycle while enforcing tenant isolation and audit provenance.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models.base import utc_now
from app.models.case import Case, CaseParcel
from app.models.parcel import Parcel
from app.models.judicial import (
    JudicialCase,
    ParcelJudicialMatch,
    MatchReviewStatus,
    ParcelMatchCategory,
)
from app.models.user import User
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError
from app.schemas.judicial import (
    JudicialCaseRecord,
    ParcelJudicialMatchResponse,
    JudicialSearchQuery,
    JudicialSearchResponse,
    JudicialManualIngestRequest,
    JudicialMatchReviewRequest,
    EPISTEMIC_JUDICIAL_DISCLAIMER,
)
from app.services.judicial.providers import get_judicial_provider, OperatorImportProvider
from app.services.judicial.matcher import JudicialEntityResolver
from app.services.judicial.classifier import JudicialRiskClassifier

logger = logging.getLogger("bhumisetu.judicial.service")


class JudicialService:
    """
    Main business orchestration service for Judicial Risk Intelligence.
    """

    def __init__(self):
        self.matcher = JudicialEntityResolver()
        self.classifier = JudicialRiskClassifier()

    def _verify_tenant_access(self, entity_org_id: Optional[uuid.UUID], current_user: User, entity_name: str) -> None:
        """Enforces multi-tenant organizational boundary check."""
        if entity_org_id and current_user.org_id and entity_org_id != current_user.org_id:
            raise CrossTenantAccessError(f"Cross-tenant access prohibited for {entity_name}.")

    async def search_and_correlate(
        self,
        db: Session,
        case_id: uuid.UUID,
        parcel_id: Optional[uuid.UUID],
        query: JudicialSearchQuery,
        current_user: User,
        provider_type: Optional[str] = None,
    ) -> JudicialSearchResponse:
        """
        Executes a judicial search across court registries, persists retrieved dockets idempotently,
        and runs deterministic entity resolution against the target parcel.
        """
        # 1. Enforce Case Tenant Isolation
        case = db.query(Case).filter(Case.case_id == case_id).first()
        if not case:
            raise EntityNotFoundError("Case", case_id)
        self._verify_tenant_access(case.org_id, current_user, "Case")

        # 2. Resolve Target Parcel
        target_parcel: Optional[Parcel] = None
        if parcel_id:
            target_parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
            if not target_parcel:
                raise EntityNotFoundError("Parcel", parcel_id)
            self._verify_tenant_access(target_parcel.org_id, current_user, "Parcel")
        else:
            # Fall back to primary case parcel or first available
            cp = db.query(CaseParcel).filter(CaseParcel.case_id == case_id, CaseParcel.is_primary == True).first()
            if not cp:
                cp = db.query(CaseParcel).filter(CaseParcel.case_id == case_id).first()
            if cp:
                target_parcel = db.query(Parcel).filter(Parcel.parcel_id == cp.parcel_id).first()

        # Build search query if user provided minimal params
        search_query = query.model_copy()
        if not search_query.party_name and target_parcel and target_parcel.recorded_raiyat:
            search_query.party_name = target_parcel.recorded_raiyat
        if not search_query.district and target_parcel and target_parcel.district:
            search_query.district = target_parcel.district

        # 3. Retrieve Cases via Provider
        provider = get_judicial_provider(provider_type)
        retrieved_cases: List[JudicialCaseRecord] = await provider.search_cases(search_query)

        persisted_cases: List[JudicialCaseRecord] = []
        match_responses: List[ParcelJudicialMatchResponse] = []

        is_direct_cnr = bool(search_query.cnr_number)

        # 4. Idempotently Persist Cases and Run Entity Resolution
        for c in retrieved_cases:
            # Reclassify based on canonical classifier rules
            risk_cat, has_inj = self.classifier.classify_case(
                c.case_type,
                c.acts_sections,
                c.orders_summary,
                c.stage_of_case,
            )

            # Check if case exists in database by unique CNR
            db_case = db.query(JudicialCase).filter(JudicialCase.cnr_number == c.cnr_number).first()
            if not db_case:
                db_case = JudicialCase(
                    case_id=uuid.uuid4(),
                    org_id=current_user.org_id,
                    cnr_number=c.cnr_number,
                    court_name=c.court_name,
                    court_type=c.court_type,
                    district=c.district,
                    state=c.state,
                    case_type=c.case_type,
                    case_number=c.case_number,
                    filing_year=c.filing_year,
                    filing_date=c.filing_date,
                    registration_date=c.registration_date,
                    case_status=c.case_status,
                    stage_of_case=c.stage_of_case,
                    petitioner_names=c.petitioner_names,
                    respondent_names=c.respondent_names,
                    advocate_petitioner=c.advocate_petitioner,
                    advocate_respondent=c.advocate_respondent,
                    acts_sections=c.acts_sections,
                    property_schedule_raw=c.property_schedule_raw,
                    extracted_land_identifiers=c.extracted_land_identifiers,
                    orders_summary=c.orders_summary,
                    has_active_injunction=has_inj,
                    risk_category=risk_cat,
                    source_url=c.source_url,
                    source_provider=c.source_provider or provider.provider_id,
                    raw_source_payload=c.model_dump(mode="json"),
                )
                db.add(db_case)
                db.flush()
            else:
                # Update status and freshness
                db_case.case_status = c.case_status
                db_case.stage_of_case = c.stage_of_case
                db_case.orders_summary = c.orders_summary
                db_case.has_active_injunction = has_inj
                db_case.risk_category = risk_cat

            persisted_cases.append(JudicialCaseRecord.model_validate(db_case))

            # Correlate with target parcel if available
            if target_parcel:
                case_dict = {
                    "cnr_number": db_case.cnr_number,
                    "court_type": db_case.court_type,
                    "district": db_case.district,
                    "extracted_land_identifiers": db_case.extracted_land_identifiers,
                    "petitioner_names": db_case.petitioner_names,
                    "respondent_names": db_case.respondent_names,
                }
                match_result = self.matcher.match_case_to_parcel(
                    parcel=target_parcel,
                    case_dict=case_dict,
                    is_direct_cnr_lookup=is_direct_cnr,
                )

                # Persist or update match record
                db_match = db.query(ParcelJudicialMatch).filter(
                    ParcelJudicialMatch.case_id == case.case_id,
                    ParcelJudicialMatch.parcel_id == target_parcel.parcel_id,
                    ParcelJudicialMatch.judicial_case_id == db_case.case_id,
                ).first()

                if not db_match:
                    db_match = ParcelJudicialMatch(
                        match_id=uuid.uuid4(),
                        org_id=current_user.org_id,
                        case_id=case.case_id,
                        parcel_id=target_parcel.parcel_id,
                        judicial_case_id=db_case.case_id,
                        match_category=match_result["match_category"],
                        confidence_score=match_result["confidence_score"],
                        matched_fields=match_result["matched_fields"],
                        matching_method=match_result["matching_method"],
                        explanation=match_result["explanation"],
                        review_status=MatchReviewStatus.PENDING_REVIEW,
                    )
                    db.add(db_match)
                    db.flush()
                else:
                    # Update scores if unreviewed
                    if db_match.review_status == MatchReviewStatus.PENDING_REVIEW:
                        db_match.match_category = match_result["match_category"]
                        db_match.confidence_score = match_result["confidence_score"]
                        db_match.matched_fields = match_result["matched_fields"]
                        db_match.explanation = match_result["explanation"]

                match_responses.append(
                    ParcelJudicialMatchResponse(
                        match_id=str(db_match.match_id),
                        case_id=str(case.case_id),
                        parcel_id=str(target_parcel.parcel_id),
                        judicial_case_id=str(db_case.case_id),
                        cnr_number=db_case.cnr_number,
                        court_name=db_case.court_name,
                        case_type=db_case.case_type,
                        case_number=db_case.case_number,
                        case_status=db_case.case_status,
                        has_active_injunction=db_case.has_active_injunction,
                        risk_category=db_case.risk_category,
                        match_category=db_match.match_category,
                        confidence_score=float(db_match.confidence_score),
                        matched_fields=db_match.matched_fields,
                        matching_method=db_match.matching_method,
                        explanation=db_match.explanation,
                        review_status=db_match.review_status,
                        reviewed_by_user_id=str(db_match.reviewed_by_user_id) if db_match.reviewed_by_user_id else None,
                        reviewed_at=db_match.reviewed_at,
                        review_notes=db_match.review_notes,
                        created_at=db_match.created_at,
                    )
                )

        db.commit()

        return JudicialSearchResponse(
            query=search_query,
            total_cases_found=len(persisted_cases),
            cases=persisted_cases,
            matches=match_responses,
            provider_used=provider.provider_id,
            retrieval_timestamp=datetime.now(timezone.utc),
            epistemic_notice=EPISTEMIC_JUDICIAL_DISCLAIMER,
        )

    def manual_ingest_case(
        self,
        db: Session,
        request: JudicialManualIngestRequest,
        current_user: User,
    ) -> JudicialCaseRecord:
        """
        Ingests a verified or certified court docket via operator-assisted channel.
        """
        import_provider = OperatorImportProvider()
        record = import_provider.normalize_and_register(request)

        # Check existing by CNR
        db_case = db.query(JudicialCase).filter(JudicialCase.cnr_number == record.cnr_number).first()
        if not db_case:
            db_case = JudicialCase(
                case_id=uuid.uuid4(),
                org_id=current_user.org_id,
                cnr_number=record.cnr_number,
                court_name=record.court_name,
                court_type=record.court_type,
                district=record.district,
                state=record.state,
                case_type=record.case_type,
                case_number=record.case_number,
                filing_year=record.filing_year,
                filing_date=record.filing_date,
                registration_date=record.registration_date,
                case_status=record.case_status,
                stage_of_case=record.stage_of_case,
                petitioner_names=record.petitioner_names,
                respondent_names=record.respondent_names,
                advocate_petitioner=record.advocate_petitioner,
                advocate_respondent=record.advocate_respondent,
                acts_sections=record.acts_sections,
                property_schedule_raw=record.property_schedule_raw,
                extracted_land_identifiers=record.extracted_land_identifiers,
                orders_summary=record.orders_summary,
                has_active_injunction=record.has_active_injunction,
                risk_category=record.risk_category,
                source_url=record.source_url,
                source_provider="OPERATOR_ASSISTED_IMPORT",
                evidence_id=uuid.UUID(record.evidence_id) if record.evidence_id else None,
                raw_source_payload=request.model_dump(mode="json"),
            )
            db.add(db_case)
        else:
            self._verify_tenant_access(db_case.org_id, current_user, "JudicialCase")
            # Update fields
            db_case.property_schedule_raw = record.property_schedule_raw
            db_case.extracted_land_identifiers = record.extracted_land_identifiers
            db_case.case_status = record.case_status
            db_case.orders_summary = record.orders_summary
            db_case.has_active_injunction = record.has_active_injunction
            db_case.risk_category = record.risk_category

        db.commit()
        db.refresh(db_case)
        return JudicialCaseRecord.model_validate(db_case)

    def review_match(
        self,
        db: Session,
        match_id: uuid.UUID,
        review_request: JudicialMatchReviewRequest,
        current_user: User,
    ) -> ParcelJudicialMatchResponse:
        """
        Records human advocate/operator review decision for a parcel-to-case link.
        """
        match = db.query(ParcelJudicialMatch).filter(ParcelJudicialMatch.match_id == match_id).first()
        if not match:
            raise EntityNotFoundError("ParcelJudicialMatch", match_id)
        self._verify_tenant_access(match.org_id, current_user, "ParcelJudicialMatch")

        action = review_request.action.upper()
        if action in ("CONFIRM_ASSOCIATED", "VERIFY"):
            match.review_status = MatchReviewStatus.VERIFIED_ASSOCIATED
        elif action in ("DISMISS_UNRELATED", "REJECT"):
            match.review_status = MatchReviewStatus.DISMISSED_UNRELATED
        elif action in ("MARK_INSUFFICIENT", "INSUFFICIENT"):
            match.review_status = MatchReviewStatus.INSUFFICIENT_EVIDENCE
        else:
            match.review_status = MatchReviewStatus.PENDING_REVIEW

        match.reviewed_by_user_id = current_user.user_id
        match.reviewed_at = utc_now()
        match.review_notes = review_request.review_notes

        db.commit()
        db.refresh(match)

        j_case = db.query(JudicialCase).filter(JudicialCase.case_id == match.judicial_case_id).first()

        return ParcelJudicialMatchResponse(
            match_id=str(match.match_id),
            case_id=str(match.case_id),
            parcel_id=str(match.parcel_id),
            judicial_case_id=str(match.judicial_case_id),
            cnr_number=j_case.cnr_number if j_case else "UNKNOWN",
            court_name=j_case.court_name if j_case else "UNKNOWN",
            case_type=j_case.case_type if j_case else "UNKNOWN",
            case_number=j_case.case_number if j_case else "UNKNOWN",
            case_status=j_case.case_status if j_case else "UNKNOWN",
            has_active_injunction=j_case.has_active_injunction if j_case else False,
            risk_category=j_case.risk_category if j_case else "OTHER",
            match_category=match.match_category,
            confidence_score=float(match.confidence_score),
            matched_fields=match.matched_fields,
            matching_method=match.matching_method,
            explanation=match.explanation,
            review_status=match.review_status,
            reviewed_by_user_id=str(match.reviewed_by_user_id),
            reviewed_at=match.reviewed_at,
            review_notes=match.review_notes,
            created_at=match.created_at,
        )

    def get_parcel_judicial_matches(
        self,
        db: Session,
        parcel_id: uuid.UUID,
        current_user: User,
    ) -> List[ParcelJudicialMatchResponse]:
        """
        Retrieves all judicial candidate matches linked to a specific parcel.
        """
        parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
        if not parcel:
            raise EntityNotFoundError("Parcel", parcel_id)
        self._verify_tenant_access(parcel.org_id, current_user, "Parcel")

        matches = db.query(ParcelJudicialMatch).filter(ParcelJudicialMatch.parcel_id == parcel_id).all()
        results: List[ParcelJudicialMatchResponse] = []

        for m in matches:
            j_case = db.query(JudicialCase).filter(JudicialCase.case_id == m.judicial_case_id).first()
            if not j_case:
                continue
            results.append(
                ParcelJudicialMatchResponse(
                    match_id=str(m.match_id),
                    case_id=str(m.case_id),
                    parcel_id=str(m.parcel_id),
                    judicial_case_id=str(m.judicial_case_id),
                    cnr_number=j_case.cnr_number,
                    court_name=j_case.court_name,
                    case_type=j_case.case_type,
                    case_number=j_case.case_number,
                    case_status=j_case.case_status,
                    has_active_injunction=j_case.has_active_injunction,
                    risk_category=j_case.risk_category,
                    match_category=m.match_category,
                    confidence_score=float(m.confidence_score),
                    matched_fields=m.matched_fields,
                    matching_method=m.matching_method,
                    explanation=m.explanation,
                    review_status=m.review_status,
                    reviewed_by_user_id=str(m.reviewed_by_user_id) if m.reviewed_by_user_id else None,
                    reviewed_at=m.reviewed_at,
                    review_notes=m.review_notes,
                    created_at=m.created_at,
                )
            )
        return results

    def get_case_judicial_summary(
        self,
        db: Session,
        case_id: uuid.UUID,
        current_user: User,
    ) -> Dict[str, Any]:
        """
        Produces an aggregated judicial risk summary for a case.
        """
        case = db.query(Case).filter(Case.case_id == case_id).first()
        if not case:
            raise EntityNotFoundError("Case", case_id)
        self._verify_tenant_access(case.org_id, current_user, "Case")

        matches = db.query(ParcelJudicialMatch).filter(ParcelJudicialMatch.case_id == case_id).all()
        active_injunctions = 0
        categories_count: Dict[str, int] = {}

        for m in matches:
            j_case = db.query(JudicialCase).filter(JudicialCase.case_id == m.judicial_case_id).first()
            if j_case:
                if j_case.has_active_injunction:
                    active_injunctions += 1
                cat = j_case.risk_category
                categories_count[cat] = categories_count.get(cat, 0) + 1

        return {
            "case_id": str(case_id),
            "total_matches": len(matches),
            "active_injunctions_detected": active_injunctions,
            "risk_categories": categories_count,
            "epistemic_notice": EPISTEMIC_JUDICIAL_DISCLAIMER,
        }
