"""
Property Passport Mutation Timeline Synchronization Service (TASK-P2-05).

Constructs a source-attributed, chronological mutation timeline for the Property Passport.
Preserves evidence provenance and enforces epistemic boundaries:
- Never overwrites historical cadastral or revenue records.
- Explicitly flags whether each observation is portal-sourced, operator-uploaded, or OCR-extracted.
- Explicitly attaches the statutory legal disclaimer (Suraj Bhan v. Financial Commissioner).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.mutation import (
    MutationCase,
    MutationEvent,
    MutationStatus,
    MutationEventType,
    MutationEntityResolution,
)
from app.schemas.mutation import (
    MutationTimelineEntry,
    PropertyPassportMutationTimelineResponse,
    STATUTORY_MUTATION_DISCLAIMER,
)

logger = logging.getLogger(__name__)

# Map event type to high-level procedural stage
EVENT_STAGE_MAP: Dict[MutationEventType, str] = {
    MutationEventType.FILING_SUBMITTED: "PETITION_SUBMISSION",
    MutationEventType.REVENUE_OFFICER_SCRUTINY: "ADMINISTRATIVE_SCRUTINY",
    MutationEventType.NOTICE_FORM_IX_ISSUED: "STATUTORY_NOTICE",
    MutationEventType.PUBLIC_OBJECTION_FILED: "OBJECTION_PROCEEDING",
    MutationEventType.HEARING_CONDUCTED: "INQUIRY_AND_HEARING",
    MutationEventType.FIELD_INQUIRY_REPORT_SUBMITTED: "FIELD_INQUIRY",
    MutationEventType.FINAL_ORDER_PASSED: "FINAL_DISPOSAL",
    MutationEventType.REJECTION_ORDER_PASSED: "ADVERSE_REJECTION",
    MutationEventType.SHUDDHI_PATRA_ISSUED: "REGISTER_II_UPDATE",
    MutationEventType.REGISTER_II_UPDATED: "REGISTER_II_UPDATE",
    MutationEventType.APPEAL_FILED_DCLR: "APPELLATE_REVIEW",
    MutationEventType.CORRECTION_SLIP_ISSUED: "REGISTER_II_UPDATE",
    MutationEventType.SOURCE_STATUS_CHANGED: "PORTAL_SYNCHRONIZATION",
}


class PropertyPassportTimelineBuilder:
    """
    Builds the unified, source-attributed chronological mutation timeline for a parcel.
    """

    @classmethod
    def build_timeline_for_parcel(
        cls,
        db: Session,
        parcel_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> PropertyPassportMutationTimelineResponse:
        """
        Retrieves all mutation proceedings associated with a parcel (direct or resolved)
        and constructs an auditable, sorted timeline.
        """
        # Find cases directly linked or resolved to this parcel
        cases = (
            db.query(MutationCase)
            .filter(
                MutationCase.org_id == org_id,
                or_(
                    MutationCase.parcel_id == parcel_id,
                    MutationCase.resolutions.any(
                        MutationEntityResolution.parcel_id == parcel_id
                    ),
                ),
            )
            .all()
        )

        all_events: List[Tuple[datetime, MutationTimelineEntry]] = []
        active_conflicts: List[Dict[str, Any]] = []

        active_proceedings_count = 0
        rejection_orders_count = 0
        approved_shuddhi_patras_count = 0
        last_synced_at: Optional[datetime] = None

        for mc in cases:
            if mc.last_source_observation:
                if not last_synced_at or mc.last_source_observation > last_synced_at:
                    last_synced_at = mc.last_source_observation

            if mc.normalized_status in (
                MutationStatus.RECEIVED,
                MutationStatus.SUBMITTED,
                MutationStatus.UNDER_SCRUTINY,
                MutationStatus.NOTICE_ISSUED,
                MutationStatus.HEARING_PENDING,
                MutationStatus.UNDER_REVIEW,
            ):
                active_proceedings_count += 1
            elif mc.normalized_status == MutationStatus.REJECTED:
                rejection_orders_count += 1
            elif mc.normalized_status == MutationStatus.APPROVED:
                approved_shuddhi_patras_count += 1
            elif mc.normalized_status == MutationStatus.CONFLICTING_EVIDENCE:
                active_conflicts.append({
                    "case_number": mc.case_number,
                    "normalized_status": mc.normalized_status.value,
                    "raw_source_status": mc.raw_source_status,
                    "rejection_reason_code": mc.rejection_reason_code,
                    "conflict_details": mc.notes or "Disagreement between source observations",
                })

            for ev in mc.events:
                t_stamp = ev.reported_event_timestamp or ev.ingested_timestamp
                stage = EVENT_STAGE_MAP.get(ev.event_type, "PROCEDURAL_EVENT")

                is_conflict = (mc.normalized_status == MutationStatus.CONFLICTING_EVIDENCE)
                entry = MutationTimelineEntry(
                    entry_id=str(ev.mutation_event_id),
                    timestamp=t_stamp,
                    stage=stage,
                    event_type=ev.event_type.value,
                    case_number=mc.case_number,
                    authority=ev.source_authority,
                    summary=ev.action_taken or f"Event {ev.event_type.value} recorded",
                    details={
                        "raw_payload": ev.raw_payload,
                        "extracted_fields": ev.extracted_fields,
                        "remarks": ev.remarks,
                        "deed_number": mc.deed_number,
                        "khata": mc.khata_number,
                        "khesra": mc.khesra_number,
                        "applicant": mc.applicant_names,
                        "seller": mc.seller_names,
                    },
                    provenance_type=ev.provenance_type,
                    confidence=1.0 if ev.provenance_type == "OFFICIAL_GOVERNMENT_PORTAL" else 0.85,
                    document_reference=ev.source_document_reference,
                    is_conflict=is_conflict,
                    conflict_details=mc.notes if is_conflict else None,
                )
                all_events.append((t_stamp, entry))

        # Sort chronologically
        all_events.sort(key=lambda x: x[0])
        timeline_entries = [item[1] for item in all_events]

        return PropertyPassportMutationTimelineResponse(
            parcel_id=str(parcel_id),
            total_cases_tracked=len(cases),
            active_proceedings_count=active_proceedings_count,
            rejection_orders_count=rejection_orders_count,
            approved_shuddhi_patras_count=approved_shuddhi_patras_count,
            active_conflicts_count=len(active_conflicts),
            timeline=timeline_entries,
            active_conflicts=active_conflicts,
            last_synced_at=last_synced_at,
            statutory_disclaimer=STATUTORY_MUTATION_DISCLAIMER,
        )
