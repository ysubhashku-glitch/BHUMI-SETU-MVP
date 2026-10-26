import os
import uuid
import hashlib
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models.user import User
from app.models.case import Case
from app.models.parcel import Parcel
from app.models.evidence import (
    Document,
    DocumentCategory,
    DocumentVersion,
    DocumentPage,
    DocumentProcessingStatus,
    Evidence,
    EvidenceType,
    AuthorityTier,
    CaseEvidence,
    EvidenceSpan,
    ExtractedField,
    ExtractedFieldStatus
)
from app.models.claim import Claim, CandidateClaim, CandidateClaimStatus
from app.core.dependencies import get_current_user
from app.core.exceptions import EntityNotFoundError, CrossTenantAccessError, BhumiSetuException
from app.core.storage import get_document_storage, validate_upload_security
from app.schemas.evidence import DocumentResponse
from app.schemas.claim import ClaimResponse
from app.schemas.document_pipeline import (
    DocumentVersionResponse,
    DocumentPageResponse,
    EvidenceSpanResponse,
    ExtractedFieldResponse,
    ExtractionReviewRequest,
    CandidateClaimResponse,
    CandidateClaimAcceptRequest,
    CandidateClaimRejectRequest,
    DocumentProcessingStatusResponse,
    DocumentClassificationResponse,
    DocumentCrossReferenceResponse,
    CrossReferenceRequest
)
from app.services.document_pipeline import DocumentPipelineService
from app.services.claim_generator_service import ClaimGeneratorService
from app.services.consistency_service import evaluate_claims_consistency
from app.services.document_classifier import DocumentClassifier
from app.services.document_cross_reference_service import DocumentCrossReferenceService
from app.services.kaithi.schemas import (
    KaithiRecognitionResult,
    KaithiReviewRequest,
    KaithiReviewResponse,
    EPISTEMIC_KAITHI_DISCLAIMER
)
from app.services.kaithi.engine import get_kaithi_engine
from app.models.base import utc_now

router = APIRouter(tags=["Documents"])

def _build_claim_response(c: Claim) -> ClaimResponse:
    return ClaimResponse(
        claim_id=str(c.claim_id),
        case_id=str(c.case_id),
        parcel_id=str(c.parcel_id),
        evidence_id=str(c.evidence_id),
        subject_entity_type=c.subject_entity_type,
        subject_id=str(c.subject_id),
        predicate=c.predicate,
        object_value=c.object_value,
        authority_tier=c.authority_tier,
        confidence_score=float(c.confidence_score),
        observed_at=c.observed_at,
        recorded_at=c.recorded_at,
        effective_from=c.effective_from,
        effective_to=c.effective_to,
        status=c.status
    )

@router.post("/cases/{case_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_case_document(
    case_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str = Form("REGISTERED_DOCUMENT"),
    auto_process: str = Form("true"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise EntityNotFoundError("Case", case_id)
    if case.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    should_process = str(auto_process).lower() in ("true", "1", "yes")
    import logging
    logging.getLogger("bhumisetu").info(f"UPLOAD DEBUG: should_process={should_process}, auto_process={auto_process}")

    raw_content = await file.read()
    detected_mime, sanitized_filename, file_size = validate_upload_security(
        content=raw_content,
        declared_filename=file.filename or "uploaded_document",
        declared_mime=file.content_type or "application/octet-stream"
    )

    storage = get_document_storage()
    storage_res = storage.put(
        content=raw_content,
        destination_name=sanitized_filename,
        mime_type=detected_mime,
        metadata={"case_id": str(case_id), "org_id": str(current_user.org_id)}
    )

    storage_uri = storage_res["storage_reference"]
    sha256_hash = storage_res["sha256_hash"]

    # 1. Create Document Entity
    document = Document(
        org_id=current_user.org_id,
        document_category=DocumentCategory.SALE_DEED if document_type == EvidenceType.REGISTERED_DOCUMENT else DocumentCategory.UNKNOWN,
        original_filename=sanitized_filename,
        mime_type=detected_mime,
        file_size_bytes=file_size,
        storage_uri=storage_uri,
        sha256_hash=sha256_hash,
        uploader_party_id=current_user.party_id if hasattr(current_user, 'party_id') else None,
        processing_status=DocumentProcessingStatus.STORED,
        document_metadata={"case_id": str(case_id), "uploaded_by_user_id": str(current_user.user_id)}
    )
    db.add(document)
    db.flush()

    # 2. Create DocumentVersion #1 (Immutable version snapshot)
    version = DocumentVersion(
        document_id=document.document_id,
        version_number=1,
        content_hash=sha256_hash,
        storage_reference=storage_uri,
        mime_type=detected_mime,
        file_size_bytes=file_size,
        processing_status=DocumentProcessingStatus.STORED
    )
    db.add(version)
    db.flush()

    # 3. Evidence Vault entry
    evidence = Evidence(
        evidence_type=document_type,
        authority_tier=AuthorityTier.STATUTORY_REGISTRY if document_type == EvidenceType.REGISTERED_DOCUMENT else AuthorityTier.USER_SUBMISSION,
        source_name=sanitized_filename,
        storage_uri=storage_uri,
        sha256_hash=sha256_hash,
        captured_by_party_id=current_user.party_id if hasattr(current_user, 'party_id') else None,
        evidence_metadata={
            "document_id": str(document.document_id),
            "version_id": str(version.version_id),
            "original_filename": sanitized_filename,
            "mime_type": detected_mime,
            "size_bytes": file_size
        }
    )
    db.add(evidence)
    db.flush()

    # 4. Associate Evidence to Case
    case_evidence = CaseEvidence(case_id=case_id, evidence_id=evidence.evidence_id)
    db.add(case_evidence)
    db.commit()
    db.refresh(document)
    db.refresh(version)

    # 5. Pipeline execution
    if should_process:
        # Run synchronous or via background task
        DocumentPipelineService.execute_pipeline(
            document_id=document.document_id,
            version_id=version.version_id,
            db=db,
            case_id=case_id
        )
        db.refresh(document)

    return DocumentResponse(
        document_id=str(document.document_id),
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size_bytes=document.file_size_bytes,
        storage_uri=document.storage_uri,
        sha256_hash=document.sha256_hash,
        processing_status=document.processing_status
    )

@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    return DocumentResponse(
        document_id=str(document.document_id),
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        file_size_bytes=document.file_size_bytes,
        storage_uri=document.storage_uri,
        sha256_hash=document.sha256_hash,
        processing_status=document.processing_status
    )

@router.get("/documents/{document_id}/pages", response_model=List[DocumentPageResponse])
def get_document_pages(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number).all()
    return [
        DocumentPageResponse(
            page_id=str(p.page_id),
            document_id=str(p.document_id) if p.document_id else None,
            version_id=str(p.version_id) if p.version_id else None,
            page_number=p.page_number,
            page_image_uri=p.page_image_uri,
            ocr_text=p.ocr_text,
            ocr_confidence=float(p.ocr_confidence) if p.ocr_confidence is not None else None,
            width_px=p.width_px,
            height_px=p.height_px,
            rotation_deg=p.rotation_deg,
            resolution_dpi=p.resolution_dpi,
            has_selectable_text=p.has_selectable_text,
            is_blank=p.is_blank,
            page_hash=p.page_hash
        )
        for p in pages
    ]

@router.get("/documents/{document_id}/processing-status", response_model=DocumentProcessingStatusResponse)
def get_document_processing_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    latest_version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id
    ).order_by(DocumentVersion.version_number.desc()).first()

    field_count = db.query(ExtractedField).filter(ExtractedField.document_id == document_id).count()
    claim_count = db.query(CandidateClaim).filter(CandidateClaim.document_id == document_id).count()

    return DocumentProcessingStatusResponse(
        document_id=str(document.document_id),
        active_version_id=str(latest_version.version_id) if latest_version else None,
        document_category=document.document_category,
        processing_status=document.processing_status,
        page_count=latest_version.page_count if latest_version else 0,
        ocr_engine=latest_version.ocr_engine if latest_version else None,
        failure_reason=latest_version.failure_reason if latest_version else None,
        extracted_field_count=field_count,
        candidate_claim_count=claim_count
    )

@router.post("/documents/{document_id}/process", response_model=DocumentVersionResponse)
def trigger_document_process(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    latest_version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id
    ).order_by(DocumentVersion.version_number.desc()).first()

    if not latest_version:
        # Create version 1 if missing
        latest_version = DocumentVersion(
            document_id=document.document_id,
            version_number=1,
            content_hash=document.sha256_hash,
            storage_reference=document.storage_uri,
            mime_type=document.mime_type,
            file_size_bytes=document.file_size_bytes
        )
        db.add(latest_version)
        db.commit()
        db.refresh(latest_version)

    # Find associated case
    case_ev = db.query(CaseEvidence).join(Evidence).filter(
        Evidence.sha256_hash == document.sha256_hash
    ).first()
    case_id = case_ev.case_id if case_ev else None

    processed_version = DocumentPipelineService.execute_pipeline(
        document_id=document.document_id,
        version_id=latest_version.version_id,
        db=db,
        case_id=case_id
    )

    return DocumentVersionResponse(
        version_id=str(processed_version.version_id),
        document_id=str(processed_version.document_id),
        version_number=processed_version.version_number,
        content_hash=processed_version.content_hash,
        storage_reference=processed_version.storage_reference,
        mime_type=processed_version.mime_type,
        file_size_bytes=processed_version.file_size_bytes,
        page_count=processed_version.page_count,
        processing_status=processed_version.processing_status,
        parser_version=processed_version.parser_version,
        ocr_engine=processed_version.ocr_engine,
        ocr_engine_version=processed_version.ocr_engine_version,
        failure_reason=processed_version.failure_reason,
        processing_started_at=processed_version.processing_started_at,
        processing_completed_at=processed_version.processing_completed_at,
        created_at=processed_version.created_at
    )

@router.get("/documents/{document_id}/extractions", response_model=List[ExtractedFieldResponse])
def get_document_extractions(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    fields = db.query(ExtractedField).filter(ExtractedField.document_id == document_id).all()
    return [
        ExtractedFieldResponse(
            field_id=str(f.field_id),
            document_id=str(f.document_id),
            version_id=str(f.version_id),
            page_id=str(f.page_id) if f.page_id else None,
            evidence_span_id=str(f.evidence_span_id) if f.evidence_span_id else None,
            field_name=f.field_name,
            raw_value=f.raw_value,
            normalized_value=f.normalized_value,
            unit=f.unit,
            data_type=f.data_type,
            extraction_method=f.extraction_method,
            confidence=float(f.confidence),
            status=f.status,
            review_notes=f.review_notes,
            reviewed_at=f.reviewed_at
        )
        for f in fields
    ]

@router.get("/documents/{document_id}/evidence-spans", response_model=List[EvidenceSpanResponse])
def get_document_evidence_spans(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    spans = db.query(EvidenceSpan).filter(EvidenceSpan.document_id == document_id).all()
    return [
        EvidenceSpanResponse(
            span_id=str(s.span_id),
            document_id=str(s.document_id),
            version_id=str(s.version_id) if s.version_id else None,
            page_id=str(s.page_id),
            x_min=s.x_min,
            y_min=s.y_min,
            x_max=s.x_max,
            y_max=s.y_max,
            char_start=s.char_start,
            char_end=s.char_end,
            extracted_text=s.extracted_text,
            source_type=s.source_type,
            extraction_method=s.extraction_method,
            confidence=float(s.confidence),
            created_at=s.created_at
        )
        for s in spans
    ]

@router.post("/extractions/{field_id}/review", response_model=ExtractedFieldResponse)
def review_extracted_field(
    field_id: uuid.UUID,
    review_req: ExtractionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    field = db.query(ExtractedField).filter(ExtractedField.field_id == field_id).first()
    if not field:
        raise EntityNotFoundError("ExtractedField", field_id)

    doc = db.query(Document).filter(Document.document_id == field.document_id).first()
    if doc and doc.org_id and doc.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    action = review_req.action.upper()
    if action == "ACCEPT":
        field.status = ExtractedFieldStatus.VALIDATED
    elif action == "EDIT":
        field.status = ExtractedFieldStatus.VALIDATED
        if review_req.reviewed_value is not None:
            field.normalized_value = review_req.reviewed_value
    elif action == "REJECT":
        field.status = ExtractedFieldStatus.REJECTED
    elif action == "MARK_UNKNOWN":
        field.status = ExtractedFieldStatus.UNKNOWN
    elif action == "MARK_CONFLICTING":
        field.status = ExtractedFieldStatus.CONFLICTING
    else:
        raise BhumiSetuException(code="INVALID_REVIEW_ACTION", message=f"Invalid action: {action}", status_code=400)

    field.review_notes = review_req.review_notes
    field.reviewed_by_user_id = current_user.user_id
    field.reviewed_at = utc_now()
    db.commit()
    db.refresh(field)

    return ExtractedFieldResponse(
        field_id=str(field.field_id),
        document_id=str(field.document_id),
        version_id=str(field.version_id),
        page_id=str(field.page_id) if field.page_id else None,
        evidence_span_id=str(field.evidence_span_id) if field.evidence_span_id else None,
        field_name=field.field_name,
        raw_value=field.raw_value,
        normalized_value=field.normalized_value,
        unit=field.unit,
        data_type=field.data_type,
        extraction_method=field.extraction_method,
        confidence=float(field.confidence),
        status=field.status,
        review_notes=field.review_notes,
        reviewed_at=field.reviewed_at
    )

@router.get("/documents/{document_id}/candidate-claims", response_model=List[CandidateClaimResponse])
def get_document_candidate_claims(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    candidates = db.query(CandidateClaim).filter(CandidateClaim.document_id == document_id).all()
    return [
        CandidateClaimResponse(
            candidate_claim_id=str(c.candidate_claim_id),
            case_id=str(c.case_id),
            document_id=str(c.document_id),
            version_id=str(c.version_id),
            extracted_field_id=str(c.extracted_field_id) if c.extracted_field_id else None,
            evidence_span_id=str(c.evidence_span_id) if c.evidence_span_id else None,
            subject_entity_type=c.subject_entity_type,
            subject_hint=c.subject_hint,
            predicate=c.predicate,
            object_value=c.object_value,
            authority_tier=c.authority_tier,
            confidence_score=float(c.confidence_score),
            status=c.status,
            materialized_claim_id=str(c.materialized_claim_id) if c.materialized_claim_id else None,
            review_notes=c.review_notes,
            reviewed_at=c.reviewed_at,
            created_at=c.created_at
        )
        for c in candidates
    ]

@router.post("/candidate-claims/{candidate_claim_id}/accept", response_model=ClaimResponse)
def accept_candidate_claim_endpoint(
    candidate_claim_id: uuid.UUID,
    req: CandidateClaimAcceptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    parcel_uuid = uuid.UUID(req.parcel_id)
    parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_uuid).first()
    if not parcel:
        raise EntityNotFoundError("Parcel", parcel_uuid)
    if parcel.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    claim = ClaimGeneratorService.accept_candidate_claim(
        candidate_claim_id=candidate_claim_id,
        user_id=current_user.user_id,
        parcel_id=parcel_uuid,
        db=db,
        review_notes=req.review_notes
    )

    # Evaluate consistency
    evaluate_claims_consistency(case_id=claim.case_id, parcel_id=parcel_uuid, db=db)

    return _build_claim_response(claim)

@router.post("/candidate-claims/{candidate_claim_id}/reject", response_model=CandidateClaimResponse)
def reject_candidate_claim_endpoint(
    candidate_claim_id: uuid.UUID,
    req: CandidateClaimRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cand = ClaimGeneratorService.reject_candidate_claim(
        candidate_claim_id=candidate_claim_id,
        user_id=current_user.user_id,
        rejection_reason=req.rejection_reason,
        db=db
    )

    return CandidateClaimResponse(
        candidate_claim_id=str(cand.candidate_claim_id),
        case_id=str(cand.case_id),
        document_id=str(cand.document_id),
        version_id=str(cand.version_id),
        extracted_field_id=str(cand.extracted_field_id) if cand.extracted_field_id else None,
        evidence_span_id=str(cand.evidence_span_id) if cand.evidence_span_id else None,
        subject_entity_type=cand.subject_entity_type,
        subject_hint=cand.subject_hint,
        predicate=cand.predicate,
        object_value=cand.object_value,
        authority_tier=cand.authority_tier,
        confidence_score=float(cand.confidence_score),
        status=cand.status,
        materialized_claim_id=str(cand.materialized_claim_id) if cand.materialized_claim_id else None,
        review_notes=cand.review_notes,
        reviewed_at=cand.reviewed_at,
        created_at=cand.created_at
    )

@router.get("/documents/{document_id}/classification", response_model=DocumentClassificationResponse)
def get_document_classification(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    meta_cls = document.document_metadata.get("classification") if document.document_metadata else None
    if meta_cls:
        return DocumentClassificationResponse(
            document_id=str(document.document_id),
            document_category=meta_cls.get("document_category", document.document_category),
            confidence=meta_cls.get("confidence", 0.90),
            method=meta_cls.get("method", "STORED_CLASSIFICATION"),
            model_version=meta_cls.get("model_version", "doc-classifier-v1.2"),
            matched_signals=meta_cls.get("matched_signals", {}),
            alternative_classifications=meta_cls.get("alternative_classifications", []),
            review_required=meta_cls.get("review_required", False),
            processing_status=meta_cls.get("processing_status", "CLASSIFIED")
        )

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number).all()
    combined_text = "\n".join(p.ocr_text for p in pages if p.ocr_text)
    cls_res = DocumentClassifier.classify(text=combined_text, filename=document.original_filename)

    return DocumentClassificationResponse(
        document_id=str(document.document_id),
        document_category=cls_res.document_category,
        confidence=cls_res.confidence,
        method=cls_res.method,
        model_version=cls_res.model_version,
        matched_signals=cls_res.matched_signals,
        alternative_classifications=cls_res.alternative_classifications,
        review_required=cls_res.review_required,
        processing_status=cls_res.processing_status
    )

@router.post("/documents/{document_id}/cross-reference", response_model=DocumentCrossReferenceResponse)
def cross_reference_document(
    document_id: uuid.UUID,
    req: Optional[CrossReferenceRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    return DocumentCrossReferenceService.cross_reference_document(
        document_id=document_id,
        org_id=current_user.org_id,
        db=db
    )


@router.post("/documents/{document_id}/kaithi-ocr", response_model=KaithiRecognitionResult)
def process_document_kaithi_ocr(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Executes specialized Kaithi Historical Vision recognition on document image.
    Generates text lines, bounding boxes, Devanagari transliteration, and confidence.
    """
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    storage = get_document_storage()
    content = storage.get(document.storage_uri)

    engine = get_kaithi_engine()
    metadata = {
        "document_category": document.document_category,
        "original_filename": document.original_filename,
        "injected_kaithi_text": document.document_metadata.get("injected_kaithi_text") if document.document_metadata else None,
        "injected_text": document.document_metadata.get("injected_text") if document.document_metadata else None
    }

    result = engine.recognize_document(
        image_bytes=content,
        document_id=str(document.document_id),
        metadata=metadata
    )

    if document.document_metadata is None:
        document.document_metadata = {}
    document.document_metadata["kaithi_ocr_result"] = result.model_dump()
    db.commit()

    return result


@router.get("/documents/{document_id}/kaithi-result", response_model=KaithiRecognitionResult)
def get_document_kaithi_result(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves latest Kaithi recognition result for document.
    """
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    if document.document_metadata and "kaithi_ocr_result" in document.document_metadata:
        return KaithiRecognitionResult(**document.document_metadata["kaithi_ocr_result"])

    storage = get_document_storage()
    content = storage.get(document.storage_uri)
    engine = get_kaithi_engine()
    metadata = {
        "document_category": document.document_category,
        "original_filename": document.original_filename,
        "injected_kaithi_text": document.document_metadata.get("injected_kaithi_text") if document.document_metadata else None,
        "injected_text": document.document_metadata.get("injected_text") if document.document_metadata else None
    }
    result = engine.recognize_document(
        image_bytes=content,
        document_id=str(document.document_id),
        metadata=metadata
    )
    if document.document_metadata is None:
        document.document_metadata = {}
    document.document_metadata["kaithi_ocr_result"] = result.model_dump()
    db.commit()
    return result


@router.post("/documents/{document_id}/kaithi-review", response_model=KaithiReviewResponse)
def submit_kaithi_human_review(
    document_id: uuid.UUID,
    review_req: KaithiReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Records human-in-the-loop review corrections for recognized Kaithi text.
    Preserves immutable raw model output and logs full audit trail.
    """
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if not document:
        raise EntityNotFoundError("Document", document_id)
    if document.org_id and document.org_id != current_user.org_id:
        raise CrossTenantAccessError()

    latest_version = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document_id
    ).order_by(DocumentVersion.version_number.desc()).first()

    now = utc_now()
    if document.document_metadata is None:
        document.document_metadata = {}

    if "kaithi_review_audit" not in document.document_metadata:
        document.document_metadata["kaithi_review_audit"] = []

    summary_entries = []
    for c in review_req.corrections:
        audit_entry = {
            "line_number": c.line_number,
            "original_raw_text": c.original_raw_text,
            "corrected_text": c.corrected_text,
            "review_notes": c.review_notes,
            "reviewed_by_user_id": str(current_user.user_id),
            "reviewed_at": now.isoformat()
        }
        document.document_metadata["kaithi_review_audit"].append(audit_entry)
        summary_entries.append(audit_entry)

    if "kaithi_ocr_result" in document.document_metadata:
        cached = document.document_metadata["kaithi_ocr_result"]
        for p in cached.get("pages", []):
            for line in p.get("lines", []):
                for c in review_req.corrections:
                    if line.get("line_number") == c.line_number:
                        line["reviewed_corrected_text"] = c.corrected_text
                        line["review_notes"] = c.review_notes
                        line["review_required"] = False
        document.document_metadata["kaithi_ocr_result"] = cached

    page = db.query(DocumentPage).filter(DocumentPage.document_id == document_id).first()
    if page:
        page.page_metadata = page.page_metadata or {}
        page.page_metadata["last_human_reviewed_at"] = now.isoformat()
        page.page_metadata["reviewed_by"] = str(current_user.user_id)
        flag_modified(page, "page_metadata")

    flag_modified(document, "document_metadata")
    db.commit()

    return KaithiReviewResponse(
        document_id=str(document.document_id),
        version_id=str(latest_version.version_id) if latest_version else "v1",
        status="REVIEWED",
        total_corrections=len(review_req.corrections),
        reviewed_at=now,
        reviewed_by_user_id=str(current_user.user_id),
        review_summary=summary_entries,
        epistemic_notice=EPISTEMIC_KAITHI_DISCLAIMER
    )


