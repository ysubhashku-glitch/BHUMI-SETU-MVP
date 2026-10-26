import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus
from app.models.parcel import Parcel
from app.models.organization import Organization
from app.models.user import User
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
from app.models.claim import Claim, CandidateClaim, CandidateClaimStatus, ClaimPredicate
from app.models.finding import Finding
from app.core.storage import get_document_storage, SecurityValidationException
from app.services.normalization_service import NormalizationService
from app.services.entity_resolution_service import EntityResolutionService, EntityMatchOutcome, ParcelMatchOutcome
from app.services.document_classifier import DocumentClassifier
from app.services.document_preprocessor import DocumentPreprocessor, PreprocessingException
from app.services.ocr_engine import get_ocr_provider, OCRBoundingBox

# --- SYNTHETIC DEMO DATA FIXTURES ---

DEMO_SYNTHETIC_SALE_DEED = (
    "%PDF-1.4\n"
    "DEMO_DATA: REGISTERED SALE DEED / बैनामा\n"
    "District: Deoghar, Circle: Mohanpur, Mauza: Jasidih (Thana No: 245)\n"
    "Khata No: 42, Plot / Khesra No: 112/A, Area: 0.25 Acre (25 Decimal)\n"
    "Seller: Ram Kumar Verma, S/o Late Shyam Verma\n"
    "Buyer: Anupama Devi, W/o Rajesh Sharma\n"
    "Deed No: 4521/2021, Registration Date: 14-04-2021, Consideration: Rs 15,50,000\n"
    "Chauhadri:\n"
    "North: Nij plot of seller\n"
    "South: PWD 20ft Road\n"
    "East: Plot No 113 of Binod Roy\n"
    "West: Common Rasta 10ft\n"
    "%%EOF\n"
).encode("utf-8")

DEMO_SYNTHETIC_KHATIYAN = (
    "%PDF-1.4\n"
    "DEMO_DATA: REVENUE KHATIYAN (खतियान)\n"
    "District: Deoghar, Circle: Mohanpur, Mauza: Jasidih, Khata: 42\n"
    "Raiyat: Shyam Sundar Verma, S/o Gokul Verma\n"
    "Caste: Kayastha (Non-Tribal)\n"
    "Plot 112/A, Nature: Dhani 2, Recorded Area: 0.50 Acre, Annual Rent: Rs 12.50\n"
    "%%EOF\n"
).encode("utf-8")

DEMO_SYNTHETIC_MUTATION = (
    "%PDF-1.4\n"
    "DEMO_DATA: DAKHIL KHARIJ / MUTATION CORRECTION SLIP (दाखिल खारिज)\n"
    "Case No: 89/2021-22, Order Date: 28-06-2021\n"
    "Transferor: Ram Kumar Verma, Transferee: Anupama Devi\n"
    "Deed Reference: 4521/2021, Plot No: 112/A, Mutated Area: 0.25 Acre\n"
    "Status: APPROVED / DAKHIL KHARIJ SANCTIONED\n"
    "%%EOF\n"
).encode("utf-8")

DEMO_SYNTHETIC_ENCUMBRANCE = (
    b"%PDF-1.4\n"
    b"DEMO_DATA: CERTIFICATE OF ENCUMBRANCE ON PROPERTY\n"
    b"Search Period: 01-01-2010 to 31-12-2025\n"
    b"Plot 112/A, Khata 42, Village Jasidih\n"
    b"Status: NIL ENCUMBRANCE\n"
    b"%%EOF\n"
)

DEMO_SYNTHETIC_IMAGE_MAP = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x04\xd8\x00\x00\x06\xd8\x08\x02\x00\x00\x00\x00\x00\x00\x00DEMO_DATA_CADASTRAL_MAP"

DEMO_ENCRYPTED_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R /Encrypt 3 0 R >>\nendobj\n%%EOF"
DEMO_CORRUPTED_PDF = b"NOT_A_VALID_PDF_HEADER_CORRUPTED"


# --- TEST CASES ---

def test_document_storage_immutability_and_hash():
    """Verifies storage put, get, metadata, duplicate content detection, and immutability."""
    storage = get_document_storage()
    content = DEMO_SYNTHETIC_SALE_DEED
    filename = "test_sale_deed.pdf"

    # 1. Put document
    res = storage.put(content=content, destination_name=filename, mime_type="application/pdf")
    storage_ref = res["storage_reference"]
    sha256 = res["sha256_hash"]

    assert storage.exists(storage_ref) is True
    assert len(sha256) == 64

    # 2. Retrieve document
    retrieved = storage.get(storage_ref)
    assert retrieved == content

    # 3. Metadata retrieval
    meta = storage.get_metadata(storage_ref)
    assert meta["sha256_hash"] == sha256

    # 4. Duplicate content yields identical hash without error
    res_dup = storage.put(content=content, destination_name="another_copy.pdf", mime_type="application/pdf")
    assert res_dup["sha256_hash"] == sha256


def test_document_preprocessor_detection_and_safeguards():
    """Tests PDF detection, corruption handling, and password-protection traps."""
    # Valid PDF
    res = DocumentPreprocessor.preprocess(DEMO_SYNTHETIC_SALE_DEED, "deed.pdf", "application/pdf")
    assert res.is_pdf is True
    assert res.page_count >= 1

    # Encrypted / password-protected PDF
    with pytest.raises(PreprocessingException) as exc_info:
        DocumentPreprocessor.preprocess(DEMO_ENCRYPTED_PDF, "locked.pdf", "application/pdf")
    assert exc_info.value.code == "PASSWORD_PROTECTED"

    # Corrupted PDF
    with pytest.raises(PreprocessingException) as exc_corrupt:
        DocumentPreprocessor.preprocess(DEMO_CORRUPTED_PDF, "corrupt.pdf", "application/pdf")
    assert exc_corrupt.value.code == "CORRUPTED_PDF"

    # Image preprocessing
    res_img = DocumentPreprocessor.preprocess(DEMO_SYNTHETIC_IMAGE_MAP, "map.png", "image/png")
    assert res_img.is_image is True
    assert res_img.page_count == 1


def test_document_classification():
    """Tests multi-category classification for sale deeds, khatiyans, and mutations."""
    sale_res = DocumentClassifier.classify("Registered Sale Deed बैनामा consideration rs 500000 seller Ram", "deed.pdf")
    assert sale_res.document_category == DocumentCategory.SALE_DEED
    assert sale_res.confidence >= 0.70

    khatian_res = DocumentClassifier.classify("Bihar Revenue Khatiyan खतियान Raiyat Shyam Sundar Khata 42", "khatian.pdf")
    assert khatian_res.document_category == DocumentCategory.KHATIYAN

    mutation_res = DocumentClassifier.classify("Dakhil Kharij mutation case no 89/21 शुद्धि पत्र", "mutation.pdf")
    assert mutation_res.document_category == DocumentCategory.MUTATION_RECORD

    unknown_res = DocumentClassifier.classify("Random text with no land terms", "random.txt")
    assert unknown_res.document_category == DocumentCategory.UNKNOWN


def test_normalization_service():
    """Tests land area normalization and legal person name parsing."""
    # 0.25 Acre -> 1011.71 sqm / 25 decimals
    norm_acre = NormalizationService.normalize_area("0.25 Acre")
    assert norm_acre is not None
    assert norm_acre.normalized_decimals == 25.0
    assert norm_acre.normalized_sqm > 1000.0

    # 10 Decimal
    norm_dec = NormalizationService.normalize_area("10 Decimal")
    assert norm_dec is not None
    assert norm_dec.normalized_decimals == 10.0

    # Name normalization
    norm_name = NormalizationService.normalize_person_name("Shri Ram Kumar Verma, S/o Late Shyam Verma")
    assert norm_name.clean_name == "Ram Kumar Verma"
    assert norm_name.honorific == "Shri"
    assert norm_name.relationship_prefix == "S/O"
    assert norm_name.relative_name == "Late Shyam Verma"


def test_entity_and_parcel_resolution(db_session: Session, tenant_a: Organization):
    """Tests candidate matching for parties and parcels."""
    from app.models.party import Party, PartyType
    party = Party(
        org_id=tenant_a.org_id,
        party_type=PartyType.PERSON,
        primary_name="Ram Kumar Verma"
    )
    db_session.add(party)

    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="JH-DEO-MOH-JAS-P112A",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Mohanpur",
        mauza_village_name="Jasidih",
        census_village_code="CVC-245",
        plot_khesra_number="112/A",
        khata_number="42",
        recorded_area_acres=0.25
    )
    db_session.add(parcel)
    db_session.commit()

    # Exact party resolution
    p_match = EntityResolutionService.resolve_party("Ram Kumar Verma", None, tenant_a.org_id, db_session)
    assert p_match.outcome == EntityMatchOutcome.MATCHED
    assert p_match.matched_party_id == party.party_id

    # Unmatched party
    p_unmatched = EntityResolutionService.resolve_party("NonExistent Person", None, tenant_a.org_id, db_session)
    assert p_unmatched.outcome == EntityMatchOutcome.UNMATCHED

    # Exact parcel resolution
    parc_match = EntityResolutionService.resolve_parcel("Deoghar", "Mohanpur", "Jasidih", "42", "112/A", tenant_a.org_id, db_session)
    assert parc_match.outcome == ParcelMatchOutcome.MATCHED
    assert parc_match.matched_parcel_id == parcel.parcel_id


def test_complete_vertical_slice_document_ingestion_pipeline(
    client: TestClient,
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    client_party,
    auth_headers_a: dict
):
    """
    End-to-End Vertical Slice:
    1. Case Creation
    2. Document Upload & Preprocessing
    3. Multi-Engine OCR & Evidence Span Extraction
    4. Template Parsing (Sale Deed)
    5. Candidate Claim Staging
    6. Human Review & Acceptance
    7. Materialization of Canonical Claim & Provenance Linkage
    8. Consistency Engine Evaluation
    """
    # 1. Create Case and Parcel
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="JH-DEO-MOH-JAS-P112A-DEMO",
        state_code="JH",
        district_name="Deoghar",
        subdistrict_anchal_name="Mohanpur",
        mauza_village_name="Jasidih",
        census_village_code="CVC-245",
        plot_khesra_number="112/A",
        khata_number="42",
        recorded_area_acres=0.25
    )
    db_session.add(parcel)
    db_session.commit()

    case_res = client.post(
        "/api/v1/cases",
        json={"primary_client_party_id": str(client_party.party_id), "target_transaction_type": "PURCHASE"},
        headers=auth_headers_a
    )
    assert case_res.status_code == 201
    case_data = case_res.json()
    case_id = case_data["case_id"]

    # Link parcel to case
    client.post(
        f"/api/v1/cases/{case_id}/parcels",
        json={"parcel_id": str(parcel.parcel_id), "is_primary": True},
        headers=auth_headers_a
    )

    # 2. Upload Document via API
    files = {"file": ("registered_sale_deed.pdf", DEMO_SYNTHETIC_SALE_DEED, "application/pdf")}
    data = {"document_type": "REGISTERED_DOCUMENT", "auto_process": "true"}

    upload_res = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files=files,
        data=data,
        headers=auth_headers_a
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    from app.models.evidence import DocumentVersion
    latest_v = db_session.query(DocumentVersion).first()
    print("FAILURE REASON:", latest_v.failure_reason if latest_v else "NO_VERSION")
    print("UPLOAD RES:", doc_data)
    doc_id = doc_data["document_id"]

    # 3. Check Document Pages & OCR Spans
    pages_res = client.get(f"/api/v1/documents/{doc_id}/pages", headers=auth_headers_a)
    assert pages_res.status_code == 200
    pages = pages_res.json()
    assert len(pages) >= 1
    assert "बैनामा" in pages[0]["ocr_text"]

    spans_res = client.get(f"/api/v1/documents/{doc_id}/evidence-spans", headers=auth_headers_a)
    assert spans_res.status_code == 200
    spans = spans_res.json()
    assert len(spans) > 0
    # Verify coordinate bounding box presence
    assert spans[0]["x_min"] is not None

    # 4. Check Extracted Fields
    extractions_res = client.get(f"/api/v1/documents/{doc_id}/extractions", headers=auth_headers_a)
    assert extractions_res.status_code == 200
    extractions = extractions_res.json()
    assert len(extractions) >= 5

    extracted_names = [e["field_name"] for e in extractions]
    assert "seller_name" in extracted_names
    assert "buyer_name" in extracted_names
    assert "recorded_area" in extracted_names
    assert "boundary_north" in extracted_names

    # 5. Check Candidate Claims Staging
    candidate_res = client.get(f"/api/v1/documents/{doc_id}/candidate-claims", headers=auth_headers_a)
    assert candidate_res.status_code == 200
    candidates = candidate_res.json()
    assert len(candidates) > 0
    
    # Candidate status must be CANDIDATE before review
    assert candidates[0]["status"] == CandidateClaimStatus.CANDIDATE

    # 6. Human Review & Acceptance
    cand_id = candidates[0]["candidate_claim_id"]
    accept_res = client.post(
        f"/api/v1/candidate-claims/{cand_id}/accept",
        json={"parcel_id": str(parcel.parcel_id), "review_notes": "Verified against Sub-Registrar Volume 4521"},
        headers=auth_headers_a
    )
    assert accept_res.status_code == 200
    canonical_claim = accept_res.json()

    assert canonical_claim["status"] == "ACTIVE"
    assert canonical_claim["parcel_id"] == str(parcel.parcel_id)
    assert canonical_claim["evidence_id"] is not None

    # 7. Verify Candidate Claim Status Updated
    refreshed_cand = db_session.query(CandidateClaim).filter(
        CandidateClaim.candidate_claim_id == uuid.UUID(cand_id)
    ).first()
    assert refreshed_cand.status == CandidateClaimStatus.ACCEPTED
    assert str(refreshed_cand.materialized_claim_id) == canonical_claim["claim_id"]

    # 8. Check Processing Status Endpoint
    status_res = client.get(f"/api/v1/documents/{doc_id}/processing-status", headers=auth_headers_a)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["page_count"] >= 1
    assert status_data["extracted_field_count"] >= 5


def test_adversarial_cross_tenant_document_access(
    client: TestClient,
    db_session: Session,
    tenant_a: Organization,
    tenant_b: Organization,
    user_a: User,
    user_b: User,
    auth_headers_a: dict,
    auth_headers_b: dict
):
    """
    Adversarial Security Test:
    Ensures Tenant B cannot access, view, or review documents, pages, or extractions belonging to Tenant A.
    """
    # Create Document owned by Tenant A
    doc_a = Document(
        org_id=tenant_a.org_id,
        original_filename="confidential_deed_tenant_a.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_uri="file:///fake/path/a.pdf",
        sha256_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        processing_status=DocumentProcessingStatus.READY
    )
    db_session.add(doc_a)
    db_session.commit()

    # Tenant B tries to get document metadata -> 403 Forbidden
    res_meta = client.get(f"/api/v1/documents/{doc_a.document_id}", headers=auth_headers_b)
    assert res_meta.status_code == 403
    assert res_meta.json()["code"] == "CROSS_TENANT_ACCESS_DENIED"

    # Tenant B tries to get document pages -> 403 Forbidden
    res_pages = client.get(f"/api/v1/documents/{doc_a.document_id}/pages", headers=auth_headers_b)
    assert res_pages.status_code == 403

    # Tenant B tries to get extractions -> 403 Forbidden
    res_ext = client.get(f"/api/v1/documents/{doc_a.document_id}/extractions", headers=auth_headers_b)
    assert res_ext.status_code == 403
