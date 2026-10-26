import uuid
from datetime import datetime, date, timezone
from enum import Enum
import sqlalchemy as sa
from sqlalchemy.orm import relationship, synonym
from app.database import Base
from app.models.base import GUID, JSONCompatible, utc_now

# =============================================================================
# Domain Enums for Bihar Mutation Lifecycle & Proceedings
# =============================================================================

class MutationType(str, Enum):
    SALE_DEED = "SALE_DEED"                 # Kewala / Registrit Bikri Patra
    INHERITANCE_WARISAN = "INHERITANCE_WARISAN" # Fauti / Warisan / Succession
    PARTITION_BATWARA = "PARTITION_BATWARA"     # Family Partition / Batwara
    GIFT_DANPATRA = "GIFT_DANPATRA"             # Registered Gift Deed
    COURT_DECREE = "COURT_DECREE"               # Civil Court Decree / Revenue Order
    WILL_WASIYAT = "WILL_WASIYAT"               # Testamentary Will
    GOVT_SETTLEMENT = "GOVT_SETTLEMENT"         # Bhoodan / Basgit Parcha / Land Grant
    OTHER = "OTHER"


class MutationStatus(str, Enum):
    RECEIVED = "RECEIVED"                       # Online petition submitted, receipt generated
    SUBMITTED = "SUBMITTED"                     # Forwarded to Halka Karamchari
    UNDER_SCRUTINY = "UNDER_SCRUTINY"           # Karamchari examining Register-II
    NOTICE_ISSUED = "NOTICE_ISSUED"             # Form-IX (प्रपत्र 9) general/specific notice published
    HEARING_PENDING = "HEARING_PENDING"         # Objections invited / hearing scheduled
    UNDER_REVIEW = "UNDER_REVIEW"               # Circle Inspector (CI) review & recommendation
    APPROVED = "APPROVED"                       # Circle Officer (CO) mutation approved
    REJECTED = "REJECTED"                       # CO rejection order passed with specific grounds
    WITHDRAWN = "WITHDRAWN"                     # Withdrawn by petitioner
    CLOSED = "CLOSED"                           # Proceeding closed
    STATUS_UNKNOWN = "STATUS_UNKNOWN"           # Missing or unmapped status
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE" # Discrepant statuses reported across sources


class MutationEventType(str, Enum):
    # Canonical Bihar Mutation Workflow Events
    FILING_SUBMITTED = "FILING_SUBMITTED"
    REVENUE_OFFICER_SCRUTINY = "REVENUE_OFFICER_SCRUTINY"
    NOTICE_FORM_IX_ISSUED = "NOTICE_FORM_IX_ISSUED"
    PUBLIC_OBJECTION_FILED = "PUBLIC_OBJECTION_FILED"
    HEARING_CONDUCTED = "HEARING_CONDUCTED"
    FIELD_INQUIRY_REPORT_SUBMITTED = "FIELD_INQUIRY_REPORT_SUBMITTED"
    FINAL_ORDER_PASSED = "FINAL_ORDER_PASSED"
    REJECTION_ORDER_PASSED = "REJECTION_ORDER_PASSED"
    SHUDDHI_PATRA_ISSUED = "SHUDDHI_PATRA_ISSUED"
    REGISTER_II_UPDATED = "REGISTER_II_UPDATED"
    APPEAL_FILED_DCLR = "APPEAL_FILED_DCLR"
    CORRECTION_SLIP_ISSUED = "CORRECTION_SLIP_ISSUED"
    SOURCE_STATUS_CHANGED = "SOURCE_STATUS_CHANGED"
    
    # Generic & System Events
    PETITION_FILED = "PETITION_FILED"
    SCRUTINY_COMPLETED = "SCRUTINY_COMPLETED"
    NOTICE_GENERATED = "NOTICE_GENERATED"
    OBJECTION_FILED = "OBJECTION_FILED"
    CI_REPORT_SUBMITTED = "CI_REPORT_SUBMITTED"
    CO_ORDER_PASSED = "CO_ORDER_PASSED"
    REJECTION_ISSUED = "REJECTION_ISSUED"
    STATUS_UPDATED = "STATUS_UPDATED"
    DOCUMENT_ATTACHED = "DOCUMENT_ATTACHED"
    RECONCILIATION_FLAGGED = "RECONCILIATION_FLAGGED"


class MutationDocumentType(str, Enum):
    MUTATION_PETITION = "MUTATION_PETITION"     # Dakhil-Kharij Application Form
    NOTICE_FORM_IX = "NOTICE_FORM_IX"           # Prapatra 9 (आम/खास सूचना)
    HEARING_NOTICE = "HEARING_NOTICE"           # Notice for personal appearance
    KARAMCHARI_REPORT = "KARAMCHARI_REPORT"     # Revenue Inspector verification report
    CI_RECOMMENDATION = "CI_RECOMMENDATION"     # Circle Inspector endorsement
    CO_APPROVAL_ORDER = "CO_APPROVAL_ORDER"     # Formal CO approval order
    REJECTION_ORDER = "REJECTION_ORDER"         # Formal rejection order with legal grounds
    SHUDDHI_PATRA = "SHUDDHI_PATRA"             # Correction Slip (जमाबंदी सुधार पत्र)
    SUPPORTING_DEED = "SUPPORTING_DEED"         # Registered Sale Deed copy


class MutationMatchingMethod(str, Enum):
    EXACT_IDENTIFIER_MATCH = "EXACT_IDENTIFIER_MATCH"       # Case number + Anchal + Mauza match
    CORROBORATED_KHATA_PLOT = "CORROBORATED_KHATA_PLOT"     # Plot, Khata, Mauza, and Seller match
    CORROBORATED_PLOT_KHATA = "CORROBORATED_PLOT_KHATA"     # Plot, Khata, Mauza, and Seller match (alias)
    DEED_REFERENCE_MATCH = "DEED_REFERENCE_MATCH"           # Exact Registered Deed No + Date match
    PARTY_NAME_CORROBORATED = "PARTY_NAME_CORROBORATED"     # Name match corroborated with village & plot
    AMBIGUOUS_MULTIPLE_CANDIDATES = "AMBIGUOUS_MULTIPLE_CANDIDATES" # Multiple potential plots found
    NAME_ONLY_MATCH_UNVERIFIED = "NAME_ONLY_MATCH_UNVERIFIED" # Name match without parcel corroboration
    MANUAL_OPERATOR_LINK = "MANUAL_OPERATOR_LINK"           # Operator verified link


class MutationVerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    OPERATOR_VERIFIED = "OPERATOR_VERIFIED"
    OFFICIAL_SOURCE_VERIFIED = "OFFICIAL_SOURCE_VERIFIED"
    REJECTED = "REJECTED"


# =============================================================================
# Database Models
# =============================================================================

class MutationCase(Base):
    """
    Represents a revenue mutation (Dakhil-Kharij) proceeding before the Circle Officer (CO).
    Retains full case lifecycle history, party declarations, and legal disposal orders.
    """
    __tablename__ = "mutation_cases"

    mutation_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="SET NULL"), nullable=True, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="SET NULL"), nullable=True, index=True)

    # Formal Bihar Revenue Identifiers
    case_number = sa.Column(sa.String(64), nullable=False, index=True) # e.g. "MUT-2024-25/DAN/1429"
    source_case_no = sa.Column(sa.String(64), nullable=True)          # e.g. "1429/2024-2025"
    financial_year = sa.Column(sa.String(16), nullable=False, default="2024-2025")

    # Administrative Jurisdiction
    district = sa.Column(sa.String(64), nullable=False, index=True)
    anchal = sa.Column(sa.String(64), nullable=False, index=True)
    halka = sa.Column(sa.String(32), nullable=True)
    mauza = sa.Column(sa.String(128), nullable=False, index=True)

    # Land Identifiers
    khata_number = sa.Column(sa.String(32), nullable=False)
    plot_khesra_number = sa.Column(sa.String(32), nullable=False, index=True)
    transferred_area_acres = sa.Column(sa.Numeric(10, 4), nullable=True)

    # Party Particulars
    applicant_name = sa.Column(sa.String(256), nullable=False)
    applicant_relation = sa.Column(sa.String(64), nullable=True)
    buyer_parties = sa.Column(JSONCompatible, nullable=False, default=list)
    seller_parties = sa.Column(JSONCompatible, nullable=False, default=list)

    # Supporting Registered Transaction
    deed_number = sa.Column(sa.String(64), nullable=True, index=True)
    deed_date = sa.Column(sa.Date, nullable=True)

    # Lifecycle State
    mutation_type = sa.Column(sa.String(64), nullable=False, default=MutationType.SALE_DEED)
    current_status = sa.Column(sa.String(32), nullable=False, default=MutationStatus.RECEIVED, index=True)
    raw_source_status = sa.Column(sa.String(128), nullable=False) # Original Hindi/English text from portal

    # Rejection & Disposal Particulars
    rejection_reason = sa.Column(sa.Text, nullable=True)
    rejection_code = sa.Column(sa.String(64), nullable=True) # e.g. "LAND_DISPUTED", "AREA_DEFICIT", "TITLE_INJUNCTION"
    filing_date = sa.Column(sa.Date, nullable=True)
    disposal_date = sa.Column(sa.Date, nullable=True)

    # Provenance and Audit
    source_authority = sa.Column(sa.String(128), nullable=False, default="BIHAR_BHUMI_DORLR")
    verification_status = sa.Column(sa.String(32), nullable=False, default=MutationVerificationStatus.UNVERIFIED)
    provenance_metadata = sa.Column(JSONCompatible, nullable=False, default=dict)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Synonyms
    circle = synonym("anchal")
    resolutions = synonym("entity_resolutions")

    # Relationships
    organization = relationship("Organization")
    parcel = relationship("Parcel", back_populates="mutation_cases")
    case = relationship("Case", back_populates="mutation_cases")
    events = relationship("MutationEvent", back_populates="mutation_case", cascade="all, delete-orphan", order_by="MutationEvent.event_date.asc()")
    documents = relationship("MutationDocument", back_populates="mutation_case", cascade="all, delete-orphan")
    entity_resolutions = relationship("MutationEntityResolution", back_populates="mutation_case", cascade="all, delete-orphan")



class MutationEvent(Base):
    """
    Chronological mutation lifecycle event ledger. Immutable once written.
    """
    __tablename__ = "mutation_events"

    event_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    mutation_id = sa.Column(GUID, sa.ForeignKey("mutation_cases.mutation_id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = sa.Column(sa.String(64), nullable=False, index=True)
    event_date = sa.Column(sa.Date, nullable=True)
    observed_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    source_authority = sa.Column(sa.String(128), nullable=False)
    source_payload = sa.Column(JSONCompatible, nullable=False, default=dict)
    payload_hash = sa.Column(sa.String(64), nullable=False) # SHA-256 for cryptographic tamper evidence

    event_description = sa.Column(sa.Text, nullable=False)
    action_taken_by = sa.Column(sa.String(128), nullable=True) # e.g. "CIRCLE_OFFICER_DANAPUR"
    source_document_ref = sa.Column(sa.String(256), nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    mutation_case = relationship("MutationCase", back_populates="events")


class MutationDocument(Base):
    """
    Stores official mutation artifacts (Form-IX notices, rejection orders, Shuddhi Patra)
    with cryptographic SHA-256 integrity and extracted field representations.
    """
    __tablename__ = "mutation_documents"

    document_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    mutation_id = sa.Column(GUID, sa.ForeignKey("mutation_cases.mutation_id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)

    document_type = sa.Column(sa.String(64), nullable=False, default=MutationDocumentType.NOTICE_FORM_IX)
    original_filename = sa.Column(sa.String(256), nullable=False)
    storage_path = sa.Column(sa.String(512), nullable=False)
    sha256_hash = sa.Column(sa.String(64), nullable=False, index=True)
    file_size_bytes = sa.Column(sa.Integer, nullable=False)

    extracted_fields = sa.Column(JSONCompatible, nullable=False, default=dict)
    ocr_confidence = sa.Column(sa.Float, nullable=True)
    review_status = sa.Column(sa.String(32), nullable=False, default="PENDING_REVIEW")

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    mutation_case = relationship("MutationCase", back_populates="documents")


class MutationEntityResolution(Base):
    """
    Evidence-grounded association between a mutation proceeding and a target parcel / case.
    Prevents erroneous name-only conflation through calibrated confidence scoring.
    """
    __tablename__ = "mutation_entity_resolutions"

    resolution_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)
    mutation_id = sa.Column(GUID, sa.ForeignKey("mutation_cases.mutation_id", ondelete="CASCADE"), nullable=False, index=True)
    parcel_id = sa.Column(GUID, sa.ForeignKey("parcels.parcel_id", ondelete="SET NULL"), nullable=True, index=True)
    case_id = sa.Column(GUID, sa.ForeignKey("cases.case_id", ondelete="SET NULL"), nullable=True, index=True)

    matching_method = sa.Column(sa.String(64), nullable=False)
    confidence_score = sa.Column(sa.Float, nullable=False)
    matching_details = sa.Column(JSONCompatible, nullable=False, default=dict)

    is_confirmed = sa.Column(sa.Boolean, nullable=False, default=False)
    reviewed_by = sa.Column(GUID, sa.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    reviewed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    mutation_case = relationship("MutationCase", back_populates="entity_resolutions")
    parcel = relationship("Parcel")
    case = relationship("Case")
    reviewer = relationship("User")


class MutationReconciliationRun(Base):
    """
    Tracks batch synchronization runs, source freshness, and error checkpoints.
    """
    __tablename__ = "mutation_reconciliation_runs"

    run_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=False, index=True)

    adapter_name = sa.Column(sa.String(64), nullable=False) # e.g. "BIHAR_BHUMI_ADAPTER", "OPERATOR_IMPORT"
    start_time = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    completion_time = sa.Column(sa.DateTime(timezone=True), nullable=True)

    records_observed = sa.Column(sa.Integer, nullable=False, default=0)
    records_new = sa.Column(sa.Integer, nullable=False, default=0)
    records_updated = sa.Column(sa.Integer, nullable=False, default=0)
    records_conflicting = sa.Column(sa.Integer, nullable=False, default=0)

    status = sa.Column(sa.String(32), nullable=False, default="IN_PROGRESS")
    error_summary = sa.Column(sa.Text, nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
