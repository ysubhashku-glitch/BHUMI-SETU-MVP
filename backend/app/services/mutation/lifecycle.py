"""
Mutation Lifecycle and State Machine Engine (TASK-P2-05).

Enforces an auditable, deterministic lifecycle state machine for Bihar Dakhil-Kharij proceedings.
Guarantees:
1. Valid progression of procedural states (RECEIVED -> NOTICE -> HEARING -> ORDER).
2. Out-of-order event arrival safety (older events never silently overwrite newer verified states).
3. Conflicting evidence preservation (disagreements flagged as CONFLICTING_EVIDENCE rather than silent resolution).
4. No unwarranted legal conclusions (approval does NOT equal ownership; absence does NOT equal clean title).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

from app.models.mutation import (
    MutationStatus,
    MutationEventType,
    MutationCase,
    MutationEvent,
)

logger = logging.getLogger(__name__)

# State precedence hierarchy: Higher value means further in procedural lifecycle
STATE_PRECEDENCE: Dict[MutationStatus, int] = {
    MutationStatus.STATUS_UNKNOWN: 0,
    MutationStatus.RECEIVED: 10,
    MutationStatus.SUBMITTED: 20,
    MutationStatus.UNDER_SCRUTINY: 30,
    MutationStatus.NOTICE_ISSUED: 40,
    MutationStatus.HEARING_PENDING: 50,
    MutationStatus.UNDER_REVIEW: 60,
    MutationStatus.WITHDRAWN: 80,
    MutationStatus.CLOSED: 85,
    MutationStatus.REJECTED: 90,
    MutationStatus.APPROVED: 90,
    MutationStatus.CONFLICTING_EVIDENCE: 100,
}

# Event type to target normalized status mapping
EVENT_TO_STATUS_MAP: Dict[MutationEventType, MutationStatus] = {
    MutationEventType.FILING_SUBMITTED: MutationStatus.SUBMITTED,
    MutationEventType.REVENUE_OFFICER_SCRUTINY: MutationStatus.UNDER_SCRUTINY,
    MutationEventType.NOTICE_FORM_IX_ISSUED: MutationStatus.NOTICE_ISSUED,
    MutationEventType.PUBLIC_OBJECTION_FILED: MutationStatus.HEARING_PENDING,
    MutationEventType.HEARING_CONDUCTED: MutationStatus.UNDER_REVIEW,
    MutationEventType.FIELD_INQUIRY_REPORT_SUBMITTED: MutationStatus.UNDER_SCRUTINY,
    MutationEventType.FINAL_ORDER_PASSED: MutationStatus.APPROVED,  # Context dependent
    MutationEventType.REJECTION_ORDER_PASSED: MutationStatus.REJECTED,
    MutationEventType.SHUDDHI_PATRA_ISSUED: MutationStatus.APPROVED,
    MutationEventType.REGISTER_II_UPDATED: MutationStatus.APPROVED,
    MutationEventType.APPEAL_FILED_DCLR: MutationStatus.UNDER_REVIEW,
    MutationEventType.CORRECTION_SLIP_ISSUED: MutationStatus.APPROVED,
    MutationEventType.SOURCE_STATUS_CHANGED: MutationStatus.UNDER_REVIEW,
}


class MutationLifecycleEngine:
    """
    Manages deterministic transitions, conflict detection, and event ordering
    for mutation proceedings.
    """

    @classmethod
    def evaluate_new_event(
        cls,
        current_status: MutationStatus,
        event_type: MutationEventType,
        event_timestamp: Optional[datetime],
        last_observation_time: Optional[datetime],
        event_payload: Dict[str, Any],
    ) -> Tuple[MutationStatus, bool, Optional[str]]:
        """
        Evaluates the impact of a newly observed lifecycle event on case status.
        Returns:
            (new_normalized_status, is_status_updated, explanation_or_conflict_note)
        """
        target_status = EVENT_TO_STATUS_MAP.get(event_type, current_status)

        # Context-dependent overrides
        if event_type == MutationEventType.FINAL_ORDER_PASSED:
            outcome = event_payload.get("outcome", "").lower()
            if "reject" in outcome or "dismiss" in outcome:
                target_status = MutationStatus.REJECTED
            elif "approve" in outcome or "sanction" in outcome:
                target_status = MutationStatus.APPROVED

        # Rule 1: Check if already in final terminal state (APPROVED, REJECTED, WITHDRAWN)
        if current_status in (MutationStatus.APPROVED, MutationStatus.REJECTED):
            # If opposite terminal event arrives, flag conflict!
            if (current_status == MutationStatus.APPROVED and target_status == MutationStatus.REJECTED) or (
                current_status == MutationStatus.REJECTED and target_status == MutationStatus.APPROVED
            ):
                return (
                    MutationStatus.CONFLICTING_EVIDENCE,
                    True,
                    f"Conflicting terminal event observed: Case was '{current_status.value}' but new event '{event_type.value}' indicates '{target_status.value}'. Both preserved for audit.",
                )

            # If an earlier procedural event (e.g. Notice) arrives after Final Order (out-of-order ingestion):
            # Preserve event in ledger without reverting terminal status!
            current_prec = STATE_PRECEDENCE.get(current_status, 0)
            target_prec = STATE_PRECEDENCE.get(target_status, 0)
            if target_prec < current_prec:
                return (
                    current_status,
                    False,
                    f"Out-of-order event ingested: '{event_type.value}' recorded in historical ledger without downgrading terminal status '{current_status.value}'.",
                )

        # Rule 2: Out-of-order event timestamp check
        if last_observation_time and event_timestamp:
            t1 = event_timestamp if event_timestamp.tzinfo else event_timestamp.replace(tzinfo=timezone.utc)
            t2 = last_observation_time if last_observation_time.tzinfo else last_observation_time.replace(tzinfo=timezone.utc)
            if t1 < t2 and STATE_PRECEDENCE.get(target_status, 0) < STATE_PRECEDENCE.get(current_status, 0):
                return (
                    current_status,
                    False,
                    f"Historical event (dated {event_timestamp.isoformat()}) ingested into ledger without reverting current status '{current_status.value}'.",
                )

        # Rule 3: Valid progression
        if STATE_PRECEDENCE.get(target_status, 0) >= STATE_PRECEDENCE.get(current_status, 0):
            return (
                target_status,
                target_status != current_status,
                f"Status updated from '{current_status.value}' to '{target_status.value}' following event '{event_type.value}'.",
            )

        return (current_status, False, None)

    @classmethod
    def reconcile_conflicting_statuses(
        cls,
        status_a: MutationStatus,
        status_b: MutationStatus,
        source_a: str,
        source_b: str,
    ) -> Tuple[MutationStatus, Dict[str, Any]]:
        """
        Preserves both source statements when two sources disagree.
        Never silently selects one over the other.
        """
        if status_a == status_b:
            return status_a, {"has_conflict": False}

        conflict_details = {
            "has_conflict": True,
            "source_a": source_a,
            "status_a": status_a.value,
            "source_b": source_b,
            "status_b": status_b.value,
            "action_taken": "Marked as CONFLICTING_EVIDENCE. Manual review required.",
        }

        return MutationStatus.CONFLICTING_EVIDENCE, conflict_details
