import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.base import utc_now
from app.models.claim import Claim, ClaimStatus, ClaimPredicate, CandidateClaim, CandidateClaimStatus
from app.models.evidence import Document, DocumentVersion, ExtractedField, Evidence, EvidenceType, AuthorityTier, CaseEvidence
from app.models.case import Case
from app.models.parcel import Parcel
from app.core.exceptions import EntityNotFoundError, BhumiSetuException

class ClaimGenerationException(BhumiSetuException):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            code="CLAIM_GENERATION_ERROR",
            message=message,
            status_code=400,
            details=details
        )

# Mapping from parsed field names to claim predicates
FIELD_TO_PREDICATE_MAP = {
    "seller_name": ClaimPredicate.SELLER,
    "buyer_name": ClaimPredicate.BUYER,
    "recorded_raiyat": ClaimPredicate.RECORDED_OWNER,
    "recorded_tenant": ClaimPredicate.RECORDED_OWNER,
    "recorded_area": ClaimPredicate.RECORDED_AREA,
    "mutated_area": ClaimPredicate.RECORDED_AREA,
    "boundary_north": ClaimPredicate.BOUNDARY_NORTH,
    "boundary_south": ClaimPredicate.BOUNDARY_SOUTH,
    "boundary_east": ClaimPredicate.BOUNDARY_EAST,
    "boundary_west": ClaimPredicate.BOUNDARY_WEST,
    "registration_number": ClaimPredicate.REGISTRATION_NUMBER,
    "deed_number": ClaimPredicate.REGISTRATION_NUMBER,
    "registration_date": ClaimPredicate.REGISTRATION_DATE,
    "mutation_status": ClaimPredicate.MUTATION_STATUS,
    "deed_reference": ClaimPredicate.DOCUMENT_REFERENCE,
}

class ClaimGeneratorService:
    """
    Transforms extracted fields into staged CandidateClaims,
    and handles human review acceptance into canonical Claims.
    """
    @classmethod
    def generate_candidate_claims_for_version(
        cls,
        case_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        db: Session
    ) -> List[CandidateClaim]:
        extracted_fields = db.query(ExtractedField).filter(
            ExtractedField.version_id == version_id
        ).all()

        candidate_claims: List[CandidateClaim] = []

        for field in extracted_fields:
            predicate = FIELD_TO_PREDICATE_MAP.get(field.field_name)
            if not predicate:
                continue

            # Skip fields with no value or UNKNOWN
            if field.raw_value in (None, "UNKNOWN") and not field.normalized_value:
                continue

            subject_type = "PARTY" if predicate in (ClaimPredicate.BUYER, ClaimPredicate.SELLER, ClaimPredicate.RECORDED_OWNER) else "PARCEL"
            
            # Formulate subject hint
            subject_hint = {
                "field_name": field.field_name,
                "raw_value": field.raw_value,
                "data_type": field.data_type
            }

            candidate_claim = CandidateClaim(
                case_id=case_id,
                document_id=document_id,
                version_id=version_id,
                extracted_field_id=field.field_id,
                evidence_span_id=field.evidence_span_id,
                subject_entity_type=subject_type,
                subject_hint=subject_hint,
                predicate=predicate,
                object_value={
                    "raw_value": field.raw_value,
                    "normalized_value": field.normalized_value,
                    "unit": field.unit
                },
                authority_tier=AuthorityTier.USER_SUBMISSION,
                confidence_score=field.confidence,
                status=CandidateClaimStatus.CANDIDATE
            )
            db.add(candidate_claim)
            candidate_claims.append(candidate_claim)

        db.flush()
        return candidate_claims

    @classmethod
    def accept_candidate_claim(
        cls,
        candidate_claim_id: uuid.UUID,
        user_id: uuid.UUID,
        parcel_id: uuid.UUID,
        db: Session,
        review_notes: Optional[str] = None
    ) -> Claim:
        candidate = db.query(CandidateClaim).filter(
            CandidateClaim.candidate_claim_id == candidate_claim_id
        ).first()

        if not candidate:
            raise EntityNotFoundError("CandidateClaim", candidate_claim_id)

        if candidate.status == CandidateClaimStatus.ACCEPTED:
            raise ClaimGenerationException("Candidate claim has already been accepted.")

        case = db.query(Case).filter(Case.case_id == candidate.case_id).first()
        if not case:
            raise EntityNotFoundError("Case", candidate.case_id)

        parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
        if not parcel:
            raise EntityNotFoundError("Parcel", parcel_id)

        # Ensure Evidence record exists in Evidence Vault for this Document
        doc = db.query(Document).filter(Document.document_id == candidate.document_id).first()
        evidence = db.query(Evidence).filter(Evidence.sha256_hash == doc.sha256_hash).first()
        if not evidence:
            evidence = Evidence(
                evidence_type=EvidenceType.REGISTERED_DOCUMENT if "DEED" in doc.document_category else EvidenceType.GOVERNMENT_RECORD,
                authority_tier=AuthorityTier.STATUTORY_REGISTRY if "DEED" in doc.document_category else AuthorityTier.REVENUE_RECORD,
                source_name=doc.original_filename,
                storage_uri=doc.storage_uri,
                sha256_hash=doc.sha256_hash,
                evidence_metadata={"document_id": str(doc.document_id), "category": doc.document_category}
            )
            db.add(evidence)
            db.flush()

        # Ensure CaseEvidence association
        case_ev = db.query(CaseEvidence).filter(
            CaseEvidence.case_id == case.case_id,
            CaseEvidence.evidence_id == evidence.evidence_id
        ).first()
        if not case_ev:
            case_ev = CaseEvidence(case_id=case.case_id, evidence_id=evidence.evidence_id)
            db.add(case_ev)
            db.flush()

        # Subject entity ID: either party or parcel
        subject_id = parcel.parcel_id

        # Materialize canonical Claim
        claim = Claim(
            case_id=case.case_id,
            parcel_id=parcel.parcel_id,
            evidence_id=evidence.evidence_id,
            subject_entity_type=candidate.subject_entity_type,
            subject_id=subject_id,
            predicate=candidate.predicate,
            object_value=candidate.object_value,
            authority_tier=evidence.authority_tier,
            confidence_score=candidate.confidence_score,
            observed_at=utc_now(),
            status=ClaimStatus.ACTIVE
        )
        db.add(claim)
        db.flush()

        # Update candidate state
        candidate.status = CandidateClaimStatus.ACCEPTED
        candidate.materialized_claim_id = claim.claim_id
        candidate.reviewed_by_user_id = user_id
        candidate.reviewed_at = utc_now()
        candidate.review_notes = review_notes or "Accepted by reviewer."
        db.commit()
        db.refresh(claim)

        return claim

    @classmethod
    def reject_candidate_claim(
        cls,
        candidate_claim_id: uuid.UUID,
        user_id: uuid.UUID,
        rejection_reason: str,
        db: Session
    ) -> CandidateClaim:
        candidate = db.query(CandidateClaim).filter(
            CandidateClaim.candidate_claim_id == candidate_claim_id
        ).first()

        if not candidate:
            raise EntityNotFoundError("CandidateClaim", candidate_claim_id)

        candidate.status = CandidateClaimStatus.REJECTED
        candidate.reviewed_by_user_id = user_id
        candidate.reviewed_at = utc_now()
        candidate.review_notes = rejection_reason
        db.commit()
        db.refresh(candidate)

        return candidate
