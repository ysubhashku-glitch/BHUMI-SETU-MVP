"""
Core Mutation Service Orchestrator (TASK-P2-05).

Provides high-level business logic for Bihar Dakhil-Kharij mutation intelligence:
- Source ingestion & adapter routing
- Cryptographic event hashing & lifecycle tracking
- Anti-name-only entity resolution
- Tenant-isolated persistence
- Property Passport synchronization
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.mutation import (
    MutationCase,
    MutationEvent,
    MutationDocument,
    MutationEntityResolution,
    MutationReconciliationRun,
    MutationType,
    MutationStatus,
    MutationEventType,
    MutationDocumentType,
    MutationMatchingMethod,
    MutationVerificationStatus,
)
from app.models.parcel import Parcel
from app.models.case import Case
from app.schemas.mutation import (
    MutationCaseCreate,
    MutationManualImportRequest,
    MutationEventCreate,
    MutationOperatorReviewRequest,
    PropertyPassportMutationTimelineResponse,
)
from app.services.mutation.adapters import get_mutation_adapter, MutationSourceAdapter
from app.services.mutation.extractor import MutationExtractor
from app.services.mutation.matcher import MutationEntityResolver
from app.services.mutation.lifecycle import MutationLifecycleEngine
from app.services.mutation.passport_timeline import PropertyPassportTimelineBuilder
from app.services.mutation.reconciliation import MutationReconciliationEngine

logger = logging.getLogger(__name__)


class MutationService:
    """
    Unified service managing mutation cases, immutable event ledgers,
    operator imports, and Property Passport integration.
    """

    def __init__(self, db: Session, adapter: Optional[MutationSourceAdapter] = None):
        self.db = db
        self.adapter = adapter or get_mutation_adapter("MOCK_ADAPTER")

    def get_case(self, case_id: uuid.UUID, org_id: uuid.UUID) -> Optional[MutationCase]:
        return (
            self.db.query(MutationCase)
            .filter(MutationCase.mutation_case_id == case_id, MutationCase.org_id == org_id)
            .first()
        )

    def get_case_by_number(self, case_number: str, district: str, circle: str, org_id: uuid.UUID) -> Optional[MutationCase]:
        return (
            self.db.query(MutationCase)
            .filter(
                MutationCase.org_id == org_id,
                MutationCase.case_number == case_number,
                MutationCase.district == district,
                MutationCase.circle == circle,
            )
            .first()
        )

    def list_cases(
        self,
        org_id: uuid.UUID,
        district: Optional[str] = None,
        circle: Optional[str] = None,
        status: Optional[MutationStatus] = None,
        parcel_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[MutationCase]:
        q = self.db.query(MutationCase).filter(MutationCase.org_id == org_id)
        if district:
            q = q.filter(MutationCase.district == district)
        if circle:
            q = q.filter(MutationCase.circle == circle)
        if status:
            q = q.filter(MutationCase.normalized_status == status)
        if parcel_id:
            q = q.filter(
                or_(
                    MutationCase.parcel_id == parcel_id,
                    MutationCase.resolutions.any(MutationEntityResolution.parcel_id == parcel_id),
                )
            )
        return q.offset(skip).limit(limit).all()

    def create_or_update_case(
        self,
        org_id: uuid.UUID,
        data: MutationCaseCreate,
    ) -> MutationCase:
        """
        Idempotently create or update a mutation proceeding without silent overwrite.
        """
        existing = self.get_case_by_number(
            case_number=data.case_number,
            district=data.district,
            circle=data.circle,
            org_id=org_id,
        )

        if existing:
            # Check for conflict
            if (
                data.normalized_status != existing.normalized_status
                and existing.normalized_status in (MutationStatus.APPROVED, MutationStatus.REJECTED)
                and data.normalized_status in (MutationStatus.APPROVED, MutationStatus.REJECTED)
            ):
                existing.normalized_status = MutationStatus.CONFLICTING_EVIDENCE
                existing.notes = (
                    f"Conflict detected between existing status '{existing.normalized_status.value}' "
                    f"and inbound status '{data.normalized_status.value}'."
                )
            elif data.normalized_status != existing.normalized_status:
                existing.normalized_status = data.normalized_status

            if data.raw_source_status:
                existing.raw_source_status = data.raw_source_status
            if data.rejection_reason_code:
                existing.rejection_reason_code = data.rejection_reason_code
            if data.rejection_reason_details:
                existing.rejection_reason_details = data.rejection_reason_details
            if data.parcel_id and not existing.parcel_id:
                existing.parcel_id = data.parcel_id
            if data.case_id and not existing.case_id:
                existing.case_id = data.case_id

            existing.last_source_observation = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        new_case = MutationCase(
            org_id=org_id,
            parcel_id=data.parcel_id,
            case_id=data.case_id,
            case_number=data.case_number,
            filing_year=data.filing_year,
            district=data.district,
            circle=data.circle,
            mauza=data.mauza,
            mutation_type=data.mutation_type,
            khata_number=data.khata_number,
            khesra_number=data.khesra_number,
            jamabandi_number=data.jamabandi_number,
            deed_number=data.deed_number,
            deed_date=data.deed_date,
            deed_registered_office=data.deed_registered_office,
            applicant_names=data.applicant_names,
            buyer_names=data.buyer_names,
            seller_names=data.seller_names,
            filing_date=data.filing_date,
            normalized_status=data.normalized_status,
            raw_source_status=data.raw_source_status,
            rejection_reason_code=data.rejection_reason_code,
            rejection_reason_details=data.rejection_reason_details,
            source_portal=data.source_portal,
            source_authority=data.source_authority,
            verification_status=MutationVerificationStatus.UNVERIFIED,
            last_source_observation=datetime.now(timezone.utc),
            notes=data.notes,
        )
        self.db.add(new_case)
        self.db.commit()
        self.db.refresh(new_case)
        return new_case

    def record_event(
        self,
        mutation_case_id: uuid.UUID,
        org_id: uuid.UUID,
        event_data: MutationEventCreate,
    ) -> MutationEvent:
        """
        Appends an immutable lifecycle event to the case ledger with cryptographic hashing.
        Safely evaluates state machine transition without rollback of verified state.
        """
        case = self.get_case(mutation_case_id, org_id)
        if not case:
            raise ValueError(f"Mutation case {mutation_case_id} not found for org {org_id}")

        # Compute SHA-256 payload hash
        payload_bytes = json.dumps(event_data.raw_payload, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        # Idempotency check: Don't duplicate exact event with same hash
        existing_event = (
            self.db.query(MutationEvent)
            .filter(
                MutationEvent.mutation_case_id == mutation_case_id,
                MutationEvent.payload_hash == payload_hash,
                MutationEvent.event_type == event_data.event_type,
            )
            .first()
        )
        if existing_event:
            return existing_event

        # Lifecycle state progression check
        new_status, is_updated, note = MutationLifecycleEngine.evaluate_new_event(
            current_status=case.normalized_status,
            event_type=event_data.event_type,
            event_timestamp=event_data.reported_event_timestamp,
            last_observation_time=case.last_source_observation,
            event_payload=event_data.raw_payload,
        )

        if is_updated:
            case.normalized_status = new_status
            if note:
                case.notes = (case.notes or "") + f" | {note}"

        case.last_source_observation = datetime.now(timezone.utc)

        event = MutationEvent(
            mutation_case_id=mutation_case_id,
            event_type=event_data.event_type,
            source_event_id=event_data.source_event_id,
            reported_event_timestamp=event_data.reported_event_timestamp,
            ingested_timestamp=datetime.now(timezone.utc),
            source_authority=event_data.source_authority,
            source_document_reference=event_data.source_document_reference,
            payload_hash=payload_hash,
            raw_payload=event_data.raw_payload,
            extracted_fields=event_data.extracted_fields,
            action_taken=event_data.action_taken,
            remarks=event_data.remarks,
            provenance_type=event_data.provenance_type,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def import_operator_case(
        self,
        org_id: uuid.UUID,
        req: MutationManualImportRequest,
        operator_user_id: Optional[uuid.UUID] = None,
    ) -> MutationCase:
        """
        Ingests a verified operator docket (order sheet, notice, Shuddhi Patra).
        Preserves provenance as OPERATOR_CERTIFIED_DOCUMENT.
        """
        normalized_status, _ = MutationExtractor.normalize_status(req.reported_status)

        case_create = MutationCaseCreate(
            case_number=req.case_number,
            filing_year=req.filing_year,
            district=req.district,
            circle=req.circle,
            mauza=req.mauza,
            mutation_type=req.mutation_type,
            khata_number=req.khata_number,
            khesra_number=req.khesra_number,
            jamabandi_number=req.jamabandi_number,
            deed_number=req.deed_number,
            deed_date=req.deed_date,
            deed_registered_office=req.deed_registered_office,
            applicant_names=[req.applicant_name] if req.applicant_name else [],
            buyer_names=[req.applicant_name] if req.applicant_name else [],
            seller_names=[req.seller_name] if req.seller_name else [],
            filing_date=req.filing_date,
            normalized_status=normalized_status,
            raw_source_status=req.reported_status,
            rejection_reason_code=req.rejection_reason_code,
            rejection_reason_details=req.rejection_reason_details,
            source_portal="OPERATOR_UPLOAD",
            source_authority="Circle Officer (Certified Docket)",
            parcel_id=req.parcel_id,
            case_id=req.case_id,
            notes=req.operator_notes,
        )

        mutation_case = self.create_or_update_case(org_id=org_id, data=case_create)

        # Ingest initial filing or order event
        event_type = MutationEventType.FILING_SUBMITTED
        action = f"Operator imported mutation proceeding: {req.case_number}"
        if normalized_status == MutationStatus.APPROVED:
            event_type = MutationEventType.SHUDDHI_PATRA_ISSUED
            action = "Certified Shuddhi Patra recorded by operator."
        elif normalized_status == MutationStatus.REJECTED:
            event_type = MutationEventType.REJECTION_ORDER_PASSED
            action = f"Certified rejection order recorded. Reason: {req.rejection_reason_code or 'Grounds in docket'}"

        self.record_event(
            mutation_case_id=mutation_case.mutation_case_id,
            org_id=org_id,
            event_data=MutationEventCreate(
                event_type=event_type,
                reported_event_timestamp=datetime.now(timezone.utc),
                source_authority="Circle Officer (Operator Ingested)",
                source_document_reference=req.certified_document_reference,
                raw_payload={"imported_by": str(operator_user_id) if operator_user_id else "OPERATOR", "case_number": req.case_number},
                action_taken=action,
                provenance_type="OPERATOR_CERTIFIED_DOCUMENT",
            ),
        )

        return mutation_case

    def resolve_parcel_association(
        self,
        mutation_case_id: uuid.UUID,
        parcel_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> MutationEntityResolution:
        """
        Evaluates and records entity resolution between a mutation case and a parcel.
        Enforces tenant isolation and anti-name-only rules.
        """
        mutation_case = self.get_case(mutation_case_id, org_id)
        if not mutation_case:
            raise ValueError(f"Mutation case {mutation_case_id} not found.")

        parcel = self.db.query(Parcel).filter(Parcel.parcel_id == parcel_id, Parcel.org_id == org_id).first()
        if not parcel:
            raise ValueError(f"Parcel {parcel_id} not found for org {org_id}.")

        eval_result = MutationEntityResolver.resolve_case_to_parcel(mutation_case, parcel)

        resolution = MutationEntityResolution(
            org_id=org_id,
            mutation_case_id=mutation_case_id,
            parcel_id=parcel_id,
            matching_method=eval_result["matching_method"],
            identifiers_compared=eval_result["identifiers_compared"],
            confidence_score=eval_result["confidence_score"],
            match_outcome=eval_result["match_outcome"],
            explanation=eval_result["explanation"],
            review_status="CONFIRMED_ASSOCIATED" if eval_result["confidence_score"] >= 0.85 else "PENDING_REVIEW",
        )
        self.db.add(resolution)

        # If high confidence match, link parcel_id to mutation_case directly
        if eval_result["confidence_score"] >= 0.85 and not mutation_case.parcel_id:
            mutation_case.parcel_id = parcel_id

        self.db.commit()
        self.db.refresh(resolution)
        return resolution

    def review_resolution(
        self,
        resolution_id: uuid.UUID,
        org_id: uuid.UUID,
        req: MutationOperatorReviewRequest,
        reviewer_user_id: uuid.UUID,
    ) -> MutationEntityResolution:
        """
        Records human operator review decision on an ambiguous entity match.
        """
        res = (
            self.db.query(MutationEntityResolution)
            .filter(MutationEntityResolution.resolution_id == resolution_id, MutationEntityResolution.org_id == org_id)
            .first()
        )
        if not res:
            raise ValueError(f"Resolution {resolution_id} not found for org {org_id}")

        if req.action == "CONFIRM_ASSOCIATION":
            res.review_status = "CONFIRMED_ASSOCIATED"
            # Link parcel to case
            mc = self.db.query(MutationCase).filter(MutationCase.mutation_case_id == res.mutation_case_id).first()
            if mc and res.parcel_id:
                mc.parcel_id = res.parcel_id
        elif req.action == "REJECT_ASSOCIATION":
            res.review_status = "REJECTED_DISMISSED"
            mc = self.db.query(MutationCase).filter(MutationCase.mutation_case_id == res.mutation_case_id).first()
            if mc and mc.parcel_id == res.parcel_id:
                mc.parcel_id = None
        else:
            res.review_status = "FLAGGED_AMBIGUOUS"

        res.reviewer_user_id = reviewer_user_id
        res.reviewed_at = datetime.now(timezone.utc)
        res.review_notes = req.review_notes

        self.db.commit()
        self.db.refresh(res)
        return res

    def get_parcel_timeline(
        self,
        parcel_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> PropertyPassportMutationTimelineResponse:
        """
        Builds chronological Property Passport mutation timeline.
        """
        return PropertyPassportTimelineBuilder.build_timeline_for_parcel(
            db=self.db,
            parcel_id=parcel_id,
            org_id=org_id,
        )

    def run_reconciliation(
        self,
        org_id: uuid.UUID,
        parcel_id: Optional[uuid.UUID] = None,
        district: Optional[str] = None,
        circle: Optional[str] = None,
    ) -> MutationReconciliationRun:
        return MutationReconciliationEngine.run_reconciliation(
            db=self.db,
            org_id=org_id,
            adapter_name=self.adapter.adapter_name,
            parcel_id=parcel_id,
            district=district,
            circle=circle,
        )

    async def get_source_health(self) -> Dict[str, Any]:
        return await self.adapter.health_check()
