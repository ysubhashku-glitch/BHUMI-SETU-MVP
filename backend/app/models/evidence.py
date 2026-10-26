import uuid
import sqlalchemy as sa
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now

class EvidenceType(str):
    GOVERNMENT_RECORD = "GOVERNMENT_RECORD"
    REGISTERED_DOCUMENT = "REGISTERED_DOCUMENT"
    USER_DOCUMENT = "USER_DOCUMENT"
    MAP = "MAP"
    GIS_RECORD = "GIS_RECORD"
    FIELD_PHOTO = "FIELD_PHOTO"
    GPS_OBSERVATION = "GPS_OBSERVATION"
    EXPERT_OBSERVATION = "EXPERT_OBSERVATION"
    LEGAL_REVIEW = "LEGAL_REVIEW"
    AI_DERIVATION = "AI_DERIVATION"

class AuthorityTier(str):
    STATUTORY_REGISTRY = "STATUTORY_REGISTRY"
    REVENUE_RECORD = "REVENUE_RECORD"
    FIELD_OBSERVATION = "FIELD_OBSERVATION"
    USER_SUBMISSION = "USER_SUBMISSION"
    AI_DERIVED = "AI_DERIVED"

class DocumentCategory(str):
    SALE_DEED = "SALE_DEED"
    GIFT_DEED = "GIFT_DEED"
    PARTITION_DEED = "PARTITION_DEED"
    MUTATION_RECORD = "MUTATION_RECORD"
    KHATIYAN = "KHATIYAN"
    JAMABANDI = "JAMABANDI"
    ENCUMBRANCE_CERTIFICATE = "ENCUMBRANCE_CERTIFICATE"
    CADASTRAL_MAP = "CADASTRAL_MAP"
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"

class DocumentProcessingStatus(str):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    STORED = "STORED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    OCR_COMPLETE = "OCR_COMPLETE"
    EXTRACTION_COMPLETE = "EXTRACTION_COMPLETE"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    READY = "READY"
    PROCESSED = "PROCESSED"  # Legacy compatibility
    NOT_PROCESSED = "NOT_PROCESSED"
    # Exceptional states
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"
    CORRUPTED = "CORRUPTED"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"
    PARTIAL = "PARTIAL"

class ExtractedFieldStatus(str):
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    CONFLICTING = "CONFLICTING"
    UNKNOWN = "UNKNOWN"

class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    evidence_type = sa.Column(sa.String(32), nullable=False)
    authority_tier = sa.Column(sa.String(32), nullable=False, default=AuthorityTier.USER_SUBMISSION)
    source_name = sa.Column(sa.String(128), nullable=False)
    storage_uri = sa.Column(sa.String(512), nullable=False)
    sha256_hash = sa.Column(sa.String(64), nullable=False, index=True)
    captured_by_party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id"), nullable=True)
    captured_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now)
    evidence_metadata = sa.Column(JSONCompatible, nullable=False, default=dict)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    case_associations = relationship("CaseEvidence", back_populates="evidence", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="evidence")

class CaseEvidence(Base):
    __tablename__ = "case_evidence"

    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="CASCADE"), primary_key=True)
    evidence_id = sa.Column(GUID, sa.ForeignKey("evidence.evidence_id", ondelete="CASCADE"), primary_key=True)
    attached_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="evidence_associations")
    evidence = relationship("Evidence", back_populates="case_associations")

class Document(Base):
    __tablename__ = "documents"

    document_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id"), nullable=True, index=True)
    document_category = sa.Column(sa.String(64), nullable=False, default=DocumentCategory.UNKNOWN, index=True)
    original_filename = sa.Column(sa.String(256), nullable=False)
    mime_type = sa.Column(sa.String(64), nullable=False)
    file_size_bytes = sa.Column(sa.Integer, nullable=False)
    storage_uri = sa.Column(sa.String(512), nullable=False)
    sha256_hash = sa.Column(sa.String(64), nullable=False, index=True)
    uploader_party_id = sa.Column(GUID, sa.ForeignKey("parties.party_id"), nullable=True)
    processing_status = sa.Column(sa.String(32), nullable=False, default=DocumentProcessingStatus.UPLOADED, index=True)
    document_metadata = sa.Column(JSONCompatible, nullable=False, default=dict)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    # Hierarchy: Document -> DocumentVersion -> DocumentPage
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    evidence_spans = relationship("EvidenceSpan", back_populates="document", cascade="all, delete-orphan")
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        case_id = kwargs.pop("case_id", None)
        super().__init__(**kwargs)
        if case_id:
            self.case_id = case_id

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    version_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    document_id = sa.Column(GUID, sa.ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = sa.Column(sa.Integer, nullable=False, default=1)
    content_hash = sa.Column(sa.String(64), nullable=False, index=True)
    storage_reference = sa.Column(sa.String(512), nullable=False)
    mime_type = sa.Column(sa.String(64), nullable=False)
    file_size_bytes = sa.Column(sa.Integer, nullable=False)
    page_count = sa.Column(sa.Integer, nullable=False, default=0)
    processing_status = sa.Column(sa.String(32), nullable=False, default=DocumentProcessingStatus.UPLOADED, index=True)
    
    # Engine & Parser tracking (Traceability)
    parser_version = sa.Column(sa.String(64), nullable=True)
    ocr_engine = sa.Column(sa.String(64), nullable=True)
    ocr_engine_version = sa.Column(sa.String(64), nullable=True)
    extraction_pipeline_version = sa.Column(sa.String(64), nullable=True)
    failure_reason = sa.Column(sa.String(512), nullable=True)
    
    processing_started_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    processing_completed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    document = relationship("Document", back_populates="versions")
    pages = relationship("DocumentPage", back_populates="version", cascade="all, delete-orphan")
    evidence_spans = relationship("EvidenceSpan", back_populates="version", cascade="all, delete-orphan")
    extracted_fields = relationship("ExtractedField", back_populates="version", cascade="all, delete-orphan")

class DocumentPage(Base):
    __tablename__ = "document_pages"

    page_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    document_id = sa.Column(GUID, sa.ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=True, index=True)
    version_id = sa.Column(GUID, sa.ForeignKey("document_versions.version_id", ondelete="CASCADE"), nullable=True, index=True)
    page_number = sa.Column(sa.Integer, nullable=False)
    page_image_uri = sa.Column(sa.String(512), nullable=True)
    ocr_text = sa.Column(sa.Text, nullable=True)
    ocr_confidence = sa.Column(sa.Numeric(5, 2), nullable=True, default=1.0)
    
    width_px = sa.Column(sa.Integer, nullable=True)
    height_px = sa.Column(sa.Integer, nullable=True)
    rotation_deg = sa.Column(sa.Integer, nullable=False, default=0)
    resolution_dpi = sa.Column(sa.Integer, nullable=True)
    has_selectable_text = sa.Column(sa.Boolean, nullable=False, default=False)
    is_blank = sa.Column(sa.Boolean, nullable=False, default=False)
    page_hash = sa.Column(sa.String(64), nullable=True)
    page_metadata = sa.Column(JSONCompatible, nullable=False, default=dict)

    document = relationship("Document", back_populates="pages")
    version = relationship("DocumentVersion", back_populates="pages")
    spans = relationship("EvidenceSpan", back_populates="page", cascade="all, delete-orphan")

class EvidenceSpan(Base):
    __tablename__ = "evidence_spans"

    span_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    document_id = sa.Column(GUID, sa.ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = sa.Column(GUID, sa.ForeignKey("document_versions.version_id", ondelete="CASCADE"), nullable=True, index=True)
    page_id = sa.Column(GUID, sa.ForeignKey("document_pages.page_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Coordinate Bounding Box (Normalized 0.0 - 1.0 or pixel coordinates)
    x_min = sa.Column(sa.Float, nullable=True)
    y_min = sa.Column(sa.Float, nullable=True)
    x_max = sa.Column(sa.Float, nullable=True)
    y_max = sa.Column(sa.Float, nullable=True)
    
    # Text character bounds
    char_start = sa.Column(sa.Integer, nullable=True)
    char_end = sa.Column(sa.Integer, nullable=True)
    
    extracted_text = sa.Column(sa.Text, nullable=False)
    source_type = sa.Column(sa.String(64), nullable=False, default="OCR")
    extraction_method = sa.Column(sa.String(64), nullable=False, default="OCR_LAYOUT")
    confidence = sa.Column(sa.Numeric(5, 2), nullable=False, default=1.0)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    document = relationship("Document", back_populates="evidence_spans")
    version = relationship("DocumentVersion", back_populates="evidence_spans")
    page = relationship("DocumentPage", back_populates="spans")
    extracted_fields = relationship("ExtractedField", back_populates="evidence_span")

class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    field_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    document_id = sa.Column(GUID, sa.ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = sa.Column(GUID, sa.ForeignKey("document_versions.version_id", ondelete="CASCADE"), nullable=False, index=True)
    page_id = sa.Column(GUID, sa.ForeignKey("document_pages.page_id", ondelete="SET NULL"), nullable=True)
    evidence_span_id = sa.Column(GUID, sa.ForeignKey("evidence_spans.span_id", ondelete="SET NULL"), nullable=True)
    
    field_name = sa.Column(sa.String(128), nullable=False, index=True)
    raw_value = sa.Column(sa.Text, nullable=True)
    normalized_value = sa.Column(JSONCompatible, nullable=True)
    unit = sa.Column(sa.String(32), nullable=True)
    data_type = sa.Column(sa.String(32), nullable=False, default="STRING")
    
    extraction_method = sa.Column(sa.String(64), nullable=False, default="TEMPLATE_RULE")
    extraction_model = sa.Column(sa.String(64), nullable=True)
    confidence = sa.Column(sa.Numeric(5, 2), nullable=False, default=1.0)
    status = sa.Column(sa.String(32), nullable=False, default=ExtractedFieldStatus.CANDIDATE, index=True)
    
    review_notes = sa.Column(sa.Text, nullable=True)
    reviewed_by_user_id = sa.Column(GUID, sa.ForeignKey("users.user_id"), nullable=True)
    reviewed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    document = relationship("Document", back_populates="extracted_fields")
    version = relationship("DocumentVersion", back_populates="extracted_fields")
    evidence_span = relationship("EvidenceSpan", back_populates="extracted_fields")
    candidate_claims = relationship("CandidateClaim", back_populates="extracted_field")
