import uuid
from datetime import datetime, date, timezone
from enum import Enum
import sqlalchemy as sa
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.ext.hybrid import hybrid_property
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
    filing_year = sa.Column(sa.Integer, nullable=True, default=2024)

    # Administrative Jurisdiction
    district = sa.Column(sa.String(64), nullable=False, index=True)
    anchal = sa.Column(sa.String(64), nullable=False, index=True)
    halka = sa.Column(sa.String(32), nullable=True)
    mauza = sa.Column(sa.String(128), nullable=False, index=True)

    # Land Identifiers
    khata_number = sa.Column(sa.String(32), nullable=False)
    plot_khesra_number = sa.Column(sa.String(32), nullable=False, index=True)
    transferred_area_acres = sa.Column(sa.Numeric(10, 4), nullable=True)
    jamabandi_number = sa.Column(sa.String(64), nullable=True)

    # Party Particulars
    applicant_name = sa.Column(sa.String(256), nullable=False)
    applicant_relation = sa.Column(sa.String(64), nullable=True)
    buyer_parties = sa.Column(JSONCompatible, nullable=False, default=list)
    seller_parties = sa.Column(JSONCompatible, nullable=False, default=list)

    # Supporting Registered Transaction
    deed_number = sa.Column(sa.String(64), nullable=True, index=True)
    deed_date = sa.Column(sa.Date, nullable=True)
    deed_registered_office = sa.Column(sa.String(128), nullable=True)

    # Lifecycle State
    _mutation_type = sa.Column("mutation_type", sa.String(64), nullable=False, default=MutationType.SALE_DEED)
    current_status = sa.Column(sa.String(32), nullable=False, default=MutationStatus.RECEIVED, index=True)
    raw_source_status = sa.Column(sa.String(128), nullable=False) # Original Hindi/English text from portal

    # Rejection & Disposal Particulars
    rejection_reason = sa.Column(sa.Text, nullable=True)
    rejection_code = sa.Column(sa.String(64), nullable=True) # e.g. "LAND_DISPUTED", "AREA_DEFICIT", "TITLE_INJUNCTION"
    filing_date = sa.Column(sa.Date, nullable=True)
    disposal_date = sa.Column(sa.Date, nullable=True)

    # Provenance and Audit
    source_authority = sa.Column(sa.String(128), nullable=False, default="BIHAR_BHUMI_DORLR")
    source_portal = sa.Column(sa.String(64), nullable=True)
    _verification_status = sa.Column("verification_status", sa.String(32), nullable=False, default=MutationVerificationStatus.UNVERIFIED)
    provenance_metadata = sa.Column(JSONCompatible, nullable=False, default=dict)
    last_source_observation = sa.Column(sa.DateTime(timezone=True), nullable=True)
    notes = sa.Column(sa.Text, nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Synonyms
    circle = synonym("anchal")
    resolutions = synonym("entity_resolutions")
    khesra_number = synonym("plot_khesra_number")
    mutation_case_id = synonym("mutation_id")
    rejection_reason_code = synonym("rejection_code")
    rejection_reason_details = synonym("rejection_reason")

    @hybrid_property
    def normalized_status(self):
        try:
            return MutationStatus(self.current_status)
        except Exception:
            return self.current_status

    @normalized_status.setter
    def normalized_status(self, val):
        if hasattr(val, "value"):
            self.current_status = val.value
        else:
            self.current_status = str(val) if val is not None else None

    @normalized_status.expression
    def normalized_status(cls):
        return cls.current_status

    @hybrid_property
    def mutation_type(self):
        try:
            return MutationType(self._mutation_type)
        except Exception:
            return self._mutation_type

    @mutation_type.setter
    def mutation_type(self, val):
        if hasattr(val, "value"):
            self._mutation_type = val.value
        else:
            self._mutation_type = str(val) if val is not None else "SALE_DEED"

    @mutation_type.expression
    def mutation_type(cls):
        return cls._mutation_type

    @hybrid_property
    def verification_status(self):
        try:
            return MutationVerificationStatus(self._verification_status)
        except Exception:
            return self._verification_status

    @verification_status.setter
    def verification_status(self, val):
        if hasattr(val, "value"):
            self._verification_status = val.value
        else:
            self._verification_status = str(val) if val is not None else "UNVERIFIED"

    @verification_status.expression
    def verification_status(cls):
        return cls._verification_status

    @property
    def applicant_names(self):
        if hasattr(self, "_applicant_names_cache") and self._applicant_names_cache:
            return self._applicant_names_cache
        return [self.applicant_name] if self.applicant_name else []

    @applicant_names.setter
    def applicant_names(self, val):
        if isinstance(val, list):
            self._applicant_names_cache = val
            self.applicant_name = val[0] if val else "Applicant"
        elif isinstance(val, str):
            self._applicant_names_cache = [val]
            self.applicant_name = val
        else:
            self._applicant_names_cache = []
            self.applicant_name = "Applicant"

    @property
    def buyer_names(self):
        return self.buyer_parties or []

    @buyer_names.setter
    def buyer_names(self, val):
        self.buyer_parties = val or []

    @property
    def seller_names(self):
        return self.seller_parties or []

    @seller_names.setter
    def seller_names(self, val):
        self.seller_parties = val or []

    # Relationships
    organization = relationship("Organization")
    parcel = relationship("Parcel", back_populates="mutation_cases")
    case = relationship("Case", back_populates="mutation_cases")
    events = relationship("MutationEvent", back_populates="mutation_case", cascade="all, delete-orphan", order_by="MutationEvent.event_date.asc()")
    documents = relationship("MutationDocument", back_populates="mutation_case", cascade="all, delete-orphan")
    entity_resolutions = relationship("MutationEntityResolution", back_populates="mutation_case", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "khesra_number" in kwargs and "plot_khesra_number" not in kwargs:
            kwargs["plot_khesra_number"] = kwargs.pop("khesra_number")
        if "plot_khesra_number" not in kwargs or not kwargs["plot_khesra_number"]:
            kwargs["plot_khesra_number"] = "UNASSIGNED"
        if "khata_number" not in kwargs or not kwargs["khata_number"]:
            kwargs["khata_number"] = "UNASSIGNED"
        if "circle" in kwargs and "anchal" not in kwargs:
            kwargs["anchal"] = kwargs.pop("circle")
        if "mutation_case_id" in kwargs and "mutation_id" not in kwargs:
            kwargs["mutation_id"] = kwargs.pop("mutation_case_id")

        if "normalized_status" in kwargs:
            val = kwargs.pop("normalized_status")
            kwargs["current_status"] = val.value if hasattr(val, "value") else str(val)
        if "current_status" in kwargs and hasattr(kwargs["current_status"], "value"):
            kwargs["current_status"] = kwargs["current_status"].value
        if "raw_source_status" not in kwargs or not kwargs["raw_source_status"]:
            kwargs["raw_source_status"] = kwargs.get("current_status", "RECEIVED")

        if "mutation_type" in kwargs and hasattr(kwargs["mutation_type"], "value"):
            kwargs["_mutation_type"] = kwargs.pop("mutation_type").value
        elif "mutation_type" in kwargs:
            kwargs["_mutation_type"] = kwargs.pop("mutation_type")

        if "verification_status" in kwargs and hasattr(kwargs["verification_status"], "value"):
            kwargs["_verification_status"] = kwargs.pop("verification_status").value
        elif "verification_status" in kwargs:
            kwargs["_verification_status"] = kwargs.pop("verification_status")

        app_names = kwargs.pop("applicant_names", None)
        if app_names:
            if isinstance(app_names, list) and app_names:
                kwargs["applicant_name"] = app_names[0]
            elif isinstance(app_names, str):
                kwargs["applicant_name"] = app_names
        if "applicant_name" not in kwargs or not kwargs["applicant_name"]:
            kwargs["applicant_name"] = "Applicant"

        if "buyer_names" in kwargs and "buyer_parties" not in kwargs:
            kwargs["buyer_parties"] = kwargs.pop("buyer_names") or []
        if "seller_names" in kwargs and "seller_parties" not in kwargs:
            kwargs["seller_parties"] = kwargs.pop("seller_names") or []

        if "rejection_reason_code" in kwargs and "rejection_code" not in kwargs:
            kwargs["rejection_code"] = kwargs.pop("rejection_reason_code")
        if "rejection_reason_details" in kwargs and "rejection_reason" not in kwargs:
            kwargs["rejection_reason"] = kwargs.pop("rejection_reason_details")

        if "filing_year" in kwargs:
            fy = kwargs["filing_year"]
            if "financial_year" not in kwargs:
                try:
                    kwargs["financial_year"] = f"{int(fy)}-{int(fy)+1}"
                except Exception:
                    kwargs["financial_year"] = str(fy)

        super().__init__(**kwargs)
        if app_names:
            self._applicant_names_cache = app_names if isinstance(app_names, list) else [app_names]



class MutationEvent(Base):
    """
    Chronological mutation lifecycle event ledger. Immutable once written.
    """
    __tablename__ = "mutation_events"

    event_id = sa.Column(GUID, primary_key=True, default=uuid.uuid4)
    mutation_id = sa.Column(GUID, sa.ForeignKey("mutation_cases.mutation_id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = sa.Column(GUID, sa.ForeignKey("organizations.org_id", ondelete="CASCADE"), nullable=True, index=True)

    event_type = sa.Column(sa.String(64), nullable=False, index=True)
    source_event_id = sa.Column(sa.String(128), nullable=True)
    event_date = sa.Column(sa.Date, nullable=True)
    observed_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    ingested_timestamp = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=True)

    source_authority = sa.Column(sa.String(128), nullable=False)
    source_payload = sa.Column(JSONCompatible, nullable=False, default=dict)
    extracted_fields = sa.Column(JSONCompatible, nullable=False, default=dict)
    payload_hash = sa.Column(sa.String(64), nullable=False) # SHA-256 for cryptographic tamper evidence

    event_description = sa.Column(sa.Text, nullable=False, default="")
    action_taken_by = sa.Column(sa.String(128), nullable=True) # e.g. "CIRCLE_OFFICER_DANAPUR"
    source_document_ref = sa.Column(sa.String(256), nullable=True)
    remarks = sa.Column(sa.Text, nullable=True)
    provenance_type = sa.Column(sa.String(64), nullable=False, default="OFFICIAL_GOVERNMENT_PORTAL")

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    # Synonyms & Hybrids
    mutation_event_id = synonym("event_id")
    mutation_case_id = synonym("mutation_id")
    raw_payload = synonym("source_payload")
    source_document_reference = synonym("source_document_ref")
    action_taken = synonym("event_description")

    @property
    def reported_event_timestamp(self):
        if self.event_date:
            return datetime.combine(self.event_date, datetime.min.time(), tzinfo=timezone.utc)
        return self.observed_at

    @reported_event_timestamp.setter
    def reported_event_timestamp(self, val):
        if val is not None:
            if hasattr(val, "date"):
                self.event_date = val.date()
            self.observed_at = val

    # Relationships
    mutation_case = relationship("MutationCase", back_populates="events")

    def __init__(self, **kwargs):
        if "mutation_case_id" in kwargs and "mutation_id" not in kwargs:
            kwargs["mutation_id"] = kwargs.pop("mutation_case_id")
        if "mutation_event_id" in kwargs and "event_id" not in kwargs:
            kwargs["event_id"] = kwargs.pop("mutation_event_id")
        if "raw_payload" in kwargs and "source_payload" not in kwargs:
            kwargs["source_payload"] = kwargs.pop("raw_payload")
        if "source_document_reference" in kwargs and "source_document_ref" not in kwargs:
            kwargs["source_document_ref"] = kwargs.pop("source_document_reference")
        if "action_taken" in kwargs and "event_description" not in kwargs:
            kwargs["event_description"] = kwargs.pop("action_taken")
        if "event_description" not in kwargs or not kwargs["event_description"]:
            kwargs["event_description"] = kwargs.get("action_taken", "MUTATION_EVENT")
        if "reported_event_timestamp" in kwargs:
            val = kwargs.pop("reported_event_timestamp")
            if val is not None:
                if hasattr(val, "date"):
                    kwargs["event_date"] = val.date()
                kwargs["observed_at"] = val
        if "event_type" in kwargs and hasattr(kwargs["event_type"], "value"):
            kwargs["event_type"] = kwargs["event_type"].value
        super().__init__(**kwargs)


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

    mutation_case_id = synonym("mutation_id")

    @hybrid_property
    def review_status(self) -> str:
        return getattr(self, "_review_status", None) or ("CONFIRMED_ASSOCIATED" if self.is_confirmed else "PENDING_REVIEW")

    @review_status.setter
    def review_status(self, val: str):
        self._review_status = val
        self.is_confirmed = (val == "CONFIRMED_ASSOCIATED")

    def __init__(self, **kwargs):
        if "mutation_case_id" in kwargs and "mutation_id" not in kwargs:
            kwargs["mutation_id"] = kwargs.pop("mutation_case_id")
        rev_status = kwargs.pop("review_status", None)
        if rev_status:
            self.review_status = rev_status
            kwargs["is_confirmed"] = (rev_status == "CONFIRMED_ASSOCIATED")
        if "matching_details" not in kwargs:
            details = {}
            for k in ["identifiers_compared", "match_outcome", "explanation"]:
                if k in kwargs:
                    details[k] = kwargs.pop(k)
            if details:
                kwargs["matching_details"] = details
        super().__init__(**kwargs)


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
    records_duplicate = sa.Column(sa.Integer, nullable=True, default=0)
    records_rejected = sa.Column(sa.Integer, nullable=True, default=0)
    records_unresolved = sa.Column(sa.Integer, nullable=True, default=0)
    records_conflicting = sa.Column(sa.Integer, nullable=False, default=0)

    status = sa.Column(sa.String(32), nullable=False, default="IN_PROGRESS")
    error_summary = sa.Column(JSONCompatible, nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    started_at = synonym("start_time")
    completed_at = synonym("completion_time")

    def __init__(self, **kwargs):
        if "started_at" in kwargs and "start_time" not in kwargs:
            kwargs["start_time"] = kwargs.pop("started_at")
        if "completed_at" in kwargs and "completion_time" not in kwargs:
            kwargs["completion_time"] = kwargs.pop("completed_at")
        super().__init__(**kwargs)
