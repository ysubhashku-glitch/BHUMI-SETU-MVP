import uuid
import time
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.base import utc_now
from app.models.evidence import (
    Document,
    DocumentCategory,
    DocumentVersion,
    DocumentPage,
    DocumentProcessingStatus,
    EvidenceSpan,
    ExtractedField,
    ExtractedFieldStatus
)
from app.core.storage import get_document_storage
from app.core.exceptions import EntityNotFoundError, BhumiSetuException
from app.services.document_preprocessor import DocumentPreprocessor, PreprocessingException
from app.services.ocr_engine import get_ocr_provider, OCRResult
from app.services.document_classifier import DocumentClassifier
from app.services.parsers import get_parser_for_category
from app.services.claim_generator_service import ClaimGeneratorService

class DocumentPipelineService:
    """
    Modular monolith document ingestion and extraction pipeline orchestrator.
    Manages state machine transitions, preprocessing, multi-engine OCR, evidence spans,
    and candidate claim generation.
    """
    PIPELINE_VERSION = "doc-pipe-v1.1"

    @classmethod
    def execute_pipeline(
        cls,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        db: Session,
        case_id: Optional[uuid.UUID] = None
    ) -> DocumentVersion:
        doc = db.query(Document).filter(Document.document_id == document_id).first()
        if not doc:
            raise EntityNotFoundError("Document", document_id)

        version = db.query(DocumentVersion).filter(DocumentVersion.version_id == version_id).first()
        if not version:
            raise EntityNotFoundError("DocumentVersion", version_id)

        storage = get_document_storage()

        # Transition: VALIDATING
        version.processing_status = DocumentProcessingStatus.VALIDATING
        doc.processing_status = DocumentProcessingStatus.VALIDATING
        version.processing_started_at = utc_now()
        db.commit()

        # Step 1: Retrieve binary content from storage boundary
        try:
            content = storage.get(version.storage_reference)
        except Exception as e:
            version.processing_status = DocumentProcessingStatus.FAILED
            doc.processing_status = DocumentProcessingStatus.FAILED
            version.failure_reason = f"Storage retrieval error: {str(e)}"
            db.commit()
            return version

        # Step 2: Preprocess document (PDF / image inspection)
        try:
            preprocess_res = DocumentPreprocessor.preprocess(
                content=content,
                original_filename=doc.original_filename,
                mime_type=version.mime_type
            )
            version.page_count = preprocess_res.page_count
        except PreprocessingException as pe:
            if pe.code == "PASSWORD_PROTECTED":
                version.processing_status = DocumentProcessingStatus.PASSWORD_PROTECTED
                doc.processing_status = DocumentProcessingStatus.PASSWORD_PROTECTED
            elif pe.code in ("CORRUPTED_PDF", "CORRUPTED_IMAGE"):
                version.processing_status = DocumentProcessingStatus.CORRUPTED
                doc.processing_status = DocumentProcessingStatus.CORRUPTED
            elif pe.code == "UNSUPPORTED_DOCUMENT_FORMAT":
                version.processing_status = DocumentProcessingStatus.UNSUPPORTED
                doc.processing_status = DocumentProcessingStatus.UNSUPPORTED
            else:
                version.processing_status = DocumentProcessingStatus.FAILED
                doc.processing_status = DocumentProcessingStatus.FAILED
            
            version.failure_reason = pe.message
            db.commit()
            return version

        # Transition: PROCESSING
        version.processing_status = DocumentProcessingStatus.PROCESSING
        doc.processing_status = DocumentProcessingStatus.PROCESSING
        db.commit()

        # Step 3: OCR Processing
        is_kaithi = False
        if doc.document_metadata:
            if doc.document_metadata.get("script") in ("KAITHI", "kai") or doc.document_metadata.get("ocr_provider") in ("kaithi", "kai"):
                is_kaithi = True
        if not is_kaithi and ("kaithi" in doc.original_filename.lower() or "cs_khatiyan" in doc.original_filename.lower()):
            is_kaithi = True

        ocr_provider = get_ocr_provider("kaithi" if is_kaithi else None)
        try:
            ocr_res: OCRResult = ocr_provider.process(
                document_content=content,
                mime_type=version.mime_type,
                metadata={
                    "document_category": doc.document_category,
                    "original_filename": doc.original_filename,
                    "injected_text": doc.document_metadata.get("injected_text") if doc.document_metadata else None,
                    "injected_kaithi_text": doc.document_metadata.get("injected_kaithi_text") if doc.document_metadata else None,
                    "script": "KAITHI" if is_kaithi else None
                }
            )
            version.ocr_engine = ocr_res.ocr_engine
            version.ocr_engine_version = ocr_res.ocr_version
        except Exception as oe:
            version.processing_status = DocumentProcessingStatus.FAILED
            doc.processing_status = DocumentProcessingStatus.FAILED
            version.failure_reason = f"OCR engine failure: {str(oe)}"
            db.commit()
            return version

        # Step 4: Decompose pages & persist OCR spans
        # Remove any previous pages for this version if re-running
        db.query(DocumentPage).filter(DocumentPage.version_id == version.version_id).delete()
        db.flush()

        page_records: Dict[int, DocumentPage] = {}
        for p_res in ocr_res.pages:
            prep_page = preprocess_res.pages[p_res.page_number - 1] if p_res.page_number <= len(preprocess_res.pages) else None
            p_hash = hashlib.sha256(p_res.full_text.encode("utf-8")).hexdigest()

            doc_page = DocumentPage(
                document_id=doc.document_id,
                version_id=version.version_id,
                page_number=p_res.page_number,
                ocr_text=p_res.full_text,
                ocr_confidence=p_res.confidence,
                width_px=prep_page.width_px if prep_page else 1240,
                height_px=prep_page.height_px if prep_page else 1754,
                rotation_deg=prep_page.rotation_deg if prep_page else 0,
                resolution_dpi=prep_page.resolution_dpi if prep_page else 150,
                has_selectable_text=prep_page.has_selectable_text if prep_page else False,
                is_blank=prep_page.is_blank if prep_page else False,
                page_hash=p_hash
            )
            db.add(doc_page)
            db.flush()
            page_records[p_res.page_number] = doc_page

            # Persist EvidenceSpans for this page
            for span in p_res.spans:
                ev_span = EvidenceSpan(
                    document_id=doc.document_id,
                    version_id=version.version_id,
                    page_id=doc_page.page_id,
                    x_min=span.bbox.x_min if span.bbox else None,
                    y_min=span.bbox.y_min if span.bbox else None,
                    x_max=span.bbox.x_max if span.bbox else None,
                    y_max=span.bbox.y_max if span.bbox else None,
                    char_start=span.char_start,
                    char_end=span.char_end,
                    extracted_text=span.text,
                    source_type="OCR",
                    extraction_method=ocr_res.ocr_engine,
                    confidence=span.confidence
                )
                db.add(ev_span)

        version.processing_status = DocumentProcessingStatus.OCR_COMPLETE
        db.commit()

        # Step 5: Document Classification
        if doc.document_category == DocumentCategory.UNKNOWN or doc.document_category == "REGISTERED_DOCUMENT":
            classification = DocumentClassifier.classify(
                text=ocr_res.combined_text,
                filename=doc.original_filename
            )
            doc.document_category = classification.document_category
            doc.document_metadata["classification"] = classification.to_dict()

        # Step 6: Template Parsing & Field Extraction
        parser = get_parser_for_category(doc.document_category)
        version.parser_version = f"{parser.PARSER_NAME}:{parser.PARSER_VERSION}"
        version.extraction_pipeline_version = cls.PIPELINE_VERSION

        parse_result = parser.parse(ocr_res)

        # Clear existing extracted fields for this version
        db.query(ExtractedField).filter(ExtractedField.version_id == version.version_id).delete()
        db.flush()

        has_low_confidence_fields = False
        first_page = page_records.get(1)

        for pf in parse_result.fields:
            if pf.confidence < 0.85:
                has_low_confidence_fields = True
            status = ExtractedFieldStatus.CANDIDATE if pf.confidence >= 0.70 else ExtractedFieldStatus.UNKNOWN
            target_page = page_records.get(pf.page_number) or first_page

            ef = ExtractedField(
                document_id=doc.document_id,
                version_id=version.version_id,
                page_id=target_page.page_id if target_page else None,
                field_name=pf.field_name,
                raw_value=pf.raw_value,
                normalized_value=pf.normalized_value,
                unit=pf.unit,
                data_type=pf.data_type,
                extraction_method=parser.PARSER_NAME,
                confidence=pf.confidence,
                status=status
            )
            db.add(ef)

        version.processing_status = DocumentProcessingStatus.EXTRACTION_COMPLETE
        db.flush()

        # Step 7: Candidate Claim Generation
        if case_id:
            ClaimGeneratorService.generate_candidate_claims_for_version(
                case_id=case_id,
                document_id=doc.document_id,
                version_id=version.version_id,
                db=db
            )

        # Step 8: Final Processing State
        if has_low_confidence_fields:
            version.processing_status = DocumentProcessingStatus.VALIDATION_REQUIRED
            doc.processing_status = DocumentProcessingStatus.VALIDATION_REQUIRED
        else:
            version.processing_status = DocumentProcessingStatus.READY
            doc.processing_status = DocumentProcessingStatus.READY

        version.processing_completed_at = utc_now()
        db.commit()
        db.refresh(version)
        db.refresh(doc)

        return version
