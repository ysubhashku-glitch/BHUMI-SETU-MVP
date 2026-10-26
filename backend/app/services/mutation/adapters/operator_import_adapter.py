"""
Operator-Assisted Ingestion Adapter for Mutation Records.

Supports compliant manual and certified document-based ingestion of Dakhil-Kharij
proceedings when automated government portals require CAPTCHA or lack public APIs.
Every ingested record retains cryptographic payload hashing and operator attribution.
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


class OperatorImportAdapter(MutationSourceAdapter):
    """
    Operator-assisted ingestion channel for certified mutation order sheets,
    Form-IX public notices, Karamchari inquiry reports, and Shuddhi Patras.
    """

    def __init__(self):
        self._in_memory_records: Dict[str, Dict[str, Any]] = {}

    @property
    def adapter_name(self) -> str:
        return "OPERATOR_ASSISTED"

    @property
    def health_status(self) -> AdapterHealthStatus:
        return AdapterHealthStatus.AVAILABLE

    def ingest_record(
        self,
        case_number: str,
        district: str,
        circle: str,
        mauza: str,
        applicant_name: str,
        seller_name: Optional[str] = None,
        khata_number: Optional[str] = None,
        khesra_number: Optional[str] = None,
        jamabandi_number: Optional[str] = None,
        deed_number: Optional[str] = None,
        deed_date: Optional[date] = None,
        mutation_type: str = "SALE_DEED",
        reported_status: str = "RECEIVED",
        filing_date: Optional[date] = None,
        order_date: Optional[date] = None,
        rejection_reason_code: Optional[str] = None,
        rejection_reason_details: Optional[str] = None,
        operator_notes: Optional[str] = None,
        certified_doc_ref: Optional[str] = None,
        operator_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate and ingest an operator-submitted mutation record.
        Generates SHA-256 payload hash and structures lifecycle event.
        """
        if not case_number or not district or not circle:
            raise MutationInvalidQueryError("Case number, district, and circle are mandatory for operator ingestion.")

        raw_payload = {
            "case_number": case_number,
            "district": district,
            "circle": circle,
            "mauza": mauza,
            "applicant_name": applicant_name,
            "seller_name": seller_name,
            "khata_number": khata_number,
            "khesra_number": khesra_number,
            "jamabandi_number": jamabandi_number,
            "deed_number": deed_number,
            "deed_date": deed_date.isoformat() if deed_date else None,
            "mutation_type": mutation_type,
            "reported_status": reported_status,
            "filing_date": filing_date.isoformat() if filing_date else None,
            "order_date": order_date.isoformat() if order_date else None,
            "rejection_reason_code": rejection_reason_code,
            "rejection_reason_details": rejection_reason_details,
            "operator_notes": operator_notes,
            "certified_doc_ref": certified_doc_ref,
            "ingested_by": operator_user_id,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        payload_bytes = json.dumps(raw_payload, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        record = {
            **raw_payload,
            "payload_hash": payload_hash,
            "source_authority": "Circle Officer (Operator Ingested)",
            "provenance_type": "OPERATOR_CERTIFIED_DOCUMENT",
            "verification_status": "UNVERIFIED",  # Never mark verified simply because operator uploaded it
            "events": [
                {
                    "event_type": "FILING_SUBMITTED",
                    "reported_timestamp": filing_date.isoformat() if filing_date else datetime.now(timezone.utc).isoformat(),
                    "action_taken": f"Mutation petition filed by {applicant_name}",
                    "source_document_reference": certified_doc_ref,
                    "payload_hash": payload_hash,
                }
            ],
        }

        if reported_status in ("APPROVED", "DISPOSED_APPROVED"):
            record["events"].append({
                "event_type": "SHUDDHI_PATRA_ISSUED",
                "reported_timestamp": order_date.isoformat() if order_date else datetime.now(timezone.utc).isoformat(),
                "action_taken": "Shuddhi Patra issued by Circle Officer",
                "source_document_reference": certified_doc_ref,
                "payload_hash": payload_hash,
            })
        elif reported_status in ("REJECTED", "DISPOSED_REJECTED"):
            record["events"].append({
                "event_type": "REJECTION_ORDER_PASSED",
                "reported_timestamp": order_date.isoformat() if order_date else datetime.now(timezone.utc).isoformat(),
                "action_taken": f"Mutation rejected by Circle Officer. Reason: {rejection_reason_code or 'Grounds in order'}",
                "source_document_reference": certified_doc_ref,
                "payload_hash": payload_hash,
            })

        key = f"{district.upper()}_{circle.upper()}_{case_number.upper()}"
        self._in_memory_records[key] = record
        return record

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
        for r in self._in_memory_records.values():
            if r["district"].lower() != district.lower() or r["circle"].lower() != circle.lower():
                continue
            if mauza and r["mauza"].lower() != mauza.lower():
                continue
            if case_number and case_number.lower() not in r["case_number"].lower():
                continue
            if khata_number and r.get("khata_number") != khata_number:
                continue
            if khesra_number and r.get("khesra_number") != khesra_number:
                continue
            if deed_number and r.get("deed_number") != deed_number:
                continue
            if applicant_name and applicant_name.lower() not in r.get("applicant_name", "").lower():
                continue
            results.append(r)
        return results

    async def get_case_detail(
        self,
        case_number: str,
        district: str,
        circle: str,
        timeout_seconds: float = 10.0,
    ) -> Optional[Dict[str, Any]]:
        key = f"{district.upper()}_{circle.upper()}_{case_number.upper()}"
        return self._in_memory_records.get(key)

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
            "ingested_records_count": len(self._in_memory_records),
            "mode": "OPERATOR_ASSISTED_INGESTION",
        }
