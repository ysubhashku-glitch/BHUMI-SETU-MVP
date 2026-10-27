"""
Mutation Reconciliation Engine (TASK-P2-05).

Identifies changes, duplicates, conflicting evidence, adverse rejection orders,
and unlinked cadastral parcels across Bihar mutation proceedings.
Logs auditable reconciliation runs and surfaces actionable intelligence alerts.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.mutation import (
    MutationCase,
    MutationStatus,
    MutationReconciliationRun,
    MutationEntityResolution,
)
from app.models.parcel import Parcel

logger = logging.getLogger(__name__)


class MutationReconciliationEngine:
    """
    Executes synchronization checks and generates discrepancies/alerts
    across mutation records.
    """

    @classmethod
    def run_reconciliation(
        cls,
        db: Session,
        org_id: uuid.UUID,
        adapter_name: str = "RECONCILIATION_ENGINE",
        parcel_id: Optional[uuid.UUID] = None,
        district: Optional[str] = None,
        circle: Optional[str] = None,
    ) -> MutationReconciliationRun:
        """
        Executes a reconciliation scan for an organization's mutation records.
        Records summary statistics and detected discrepancies into MutationReconciliationRun.
        """
        run = MutationReconciliationRun(
            org_id=org_id,
            adapter_name=adapter_name,
            started_at=datetime.now(timezone.utc),
            status="RUNNING",
        )
        db.add(run)
        db.flush()

        query = db.query(MutationCase).filter(MutationCase.org_id == org_id)
        if parcel_id:
            query = query.filter(MutationCase.parcel_id == parcel_id)
        if district:
            query = query.filter(MutationCase.district == district)
        if circle:
            query = query.filter(MutationCase.circle == circle)

        cases = query.all()

        records_observed = len(cases)
        records_new = 0
        records_updated = 0
        records_duplicate = 0
        records_rejected = 0
        records_unresolved = 0
        records_conflicting = 0

        deed_map: Dict[str, List[MutationCase]] = {}
        error_details: List[Dict[str, Any]] = []

        now_utc = datetime.now(timezone.utc)
        stale_threshold = now_utc - timedelta(days=180)

        for mc in cases:
            # 1. Check for Rejection orders
            if mc.normalized_status == MutationStatus.REJECTED:
                records_rejected += 1

            # 2. Check for Conflicting evidence
            if mc.normalized_status == MutationStatus.CONFLICTING_EVIDENCE:
                records_conflicting += 1
                error_details.append({
                    "case_number": mc.case_number,
                    "issue_type": "CONFLICTING_EVIDENCE",
                    "details": mc.notes or "Conflicting observations between sources",
                })

            # 3. Check for Unlinked / Unresolved parcels
            if not mc.parcel_id:
                has_active_resolution = db.query(MutationEntityResolution).filter(
                    MutationEntityResolution.mutation_id == mc.mutation_id,
                    MutationEntityResolution.is_confirmed == True,
                ).first()
                if not has_active_resolution:
                    records_unresolved += 1

            # 4. Check for duplicate deed submissions
            if mc.deed_number:
                key = f"{mc.district.upper()}_{mc.circle.upper()}_{mc.deed_number.upper()}"
                deed_map.setdefault(key, []).append(mc)

            # 5. Stale proceedings check
            if mc.normalized_status in (
                MutationStatus.RECEIVED,
                MutationStatus.SUBMITTED,
                MutationStatus.UNDER_SCRUTINY,
                MutationStatus.NOTICE_ISSUED,
                MutationStatus.HEARING_PENDING,
            ):
                created_tz = mc.created_at if mc.created_at.tzinfo else mc.created_at.replace(tzinfo=timezone.utc)
                if created_tz < stale_threshold:
                    error_details.append({
                        "case_number": mc.case_number,
                        "issue_type": "STALE_PROCEEDING",
                        "details": f"Proceeding pending > 180 days without disposal order (Status: {mc.normalized_status.value}).",
                    })

        # Process duplicates
        for key, dup_cases in deed_map.items():
            if len(dup_cases) > 1:
                records_duplicate += (len(dup_cases) - 1)
                error_details.append({
                    "deed_key": key,
                    "issue_type": "DUPLICATE_DEED_SUBMISSION",
                    "cases": [c.case_number for c in dup_cases],
                    "details": f"Multiple mutation petitions ({len(dup_cases)}) registered for deed '{dup_cases[0].deed_number}'.",
                })

        run.completed_at = datetime.now(timezone.utc)
        run.records_observed = records_observed
        run.records_new = records_new
        run.records_updated = records_updated
        run.records_duplicate = records_duplicate
        run.records_rejected = records_rejected
        run.records_unresolved = records_unresolved
        run.records_conflicting = records_conflicting
        run.status = "COMPLETED"
        run.error_summary = {
            "discrepancy_count": len(error_details),
            "discrepancies": error_details,
        }

        db.commit()
        db.refresh(run)
        return run
