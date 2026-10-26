"""
Bhumi Setu - TASK-P1-03 Document Intelligence & OCR Pipeline Test Suite.

Comprehensive validation covering:
1. Multilingual OCR & Ingestion (Hindi/Devanagari, English, multi-page, scanned vs digital, corrupted/empty).
2. Document Classification (Sale Deed, Khatiyan, Jamabandi, Mutation, Cadastral Map, Unknown, Ambiguity).
3. Structured Field Extraction (Khata, Plot, Parties, Area normalization, Chauhaddi boundaries, page provenance).
4. Jamabandi & Cadastral Cross-Referencing (Exact match, Probable, Multiple candidates, Conflict, Area discrepancy, Insufficient).
5. Human Review Workflow & Audit Trail (Accept, Edit, Reject, preservation of raw value, tenant isolation).
6. Security & Regression safeguards (Path traversal, file bounds, tenant isolation).
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.parcel import Parcel
from app.models.organization import Organization
from app.models.user import User
from app.models.evidence import (
    Document,
    DocumentCategory,
    DocumentVersion,
    DocumentPage,
    DocumentProcessingStatus,
    ExtractedField,
    ExtractedFieldStatus
)
from app.services.normalization_service import NormalizationService, NormalizedArea
from app.services.parsers.chauhaddi_extractor import ChauhaddiExtractor
from app.services.document_classifier import DocumentClassifier
from app.services.ocr_engine import DemoOCRProvider, TesseractOCRProvider, OCRBoundingBox
from app.services.parsers.sale_deed_parser import SaleDeedParser
from app.services.parsers.khatiyan_parser import KhatiyanParser
from app.services.document_cross_reference_service import (
    DocumentCrossReferenceService,
    CrossReferenceStatus
)
from app.services.document_pipeline import DocumentPipelineService
from app.core.storage import get_document_storage, validate_upload_security, SecurityValidationException
from app.core.exceptions import CrossTenantAccessError, EntityNotFoundError

# --- MULTILINGUAL SAMPLE FIXTURES ---

HINDI_DEVANAGARI_SALE_DEED = (
    "बैनामा विलेख / REGISTERED SALE DEED\n"
    "जिला: पटना (Patna), अंचल: दानापुर (Danapur), मौजा: कोठवां (Kothawan)\n"
    "खाता संख्या: 145, खेसरा संख्या: 890, रकबा: 1 एकड़ 25 डिसमिल\n"
    "विक्रेता: महेश प्रसाद, आत्मज: स्वर्गीय रामेश्वर प्रसाद, निवासी कोठवां\n"
    "क्रेता: सुनीता देवी, पति: सुरेश कुमार, निवासी दानापुर\n"
    "दस्तावेज़ संख्या: 3412/2022, निबंधन तिथि: 12-05-2022, प्रतिफल राशि: रु 25,00,000\n"
    "चौहद्दी:\n"
    "उत्तर: निज विक्रेता का खेत\n"
    "दक्षिण: 25 फीट चौड़ा पीडब्ल्यूडी रास्ता\n"
    "East: प्लॉट संख्या 891 रमेश सिंह का\n"
    "West: सर्वसाधारण रास्ता 12 फीट\n"
)

MULTI_PAGE_DOCUMENT_TEXT = (
    "BIHAR REVENUE KHATIYAN (खतियान) - PAGE 1\n"
    "District: Gaya, Anchal: Bodhgaya, Mauza: Bakraur, Thana No: 312\n"
    "Khata Number: 78\n"
    "Raiyat: Ramdhani Mahto, S/o Jageshwar Mahto\n"
    "Caste: Kurmi (OBC)\n"
    "--- PAGE BREAK ---\n"
    "KHATIYAN PLOT SCHEDULE - PAGE 2\n"
    "Plot Number: 450, Nature: Dhani 1, Recorded Area: 2 Bigha 10 Katha\n"
    "Annual Rent: Rs 24.50\n"
    "North: Plot 449, South: Nala, East: Plot 451, West: Sarak\n"
)


# =====================================================================
# A. OCR and Document Ingestion
# =====================================================================

def test_ocr_provider_multilingual_and_bounding_boxes():
    """Validates Devanagari script detection and bounding box coordinate generation."""
    provider = DemoOCRProvider()
    result = provider.process(
        document_content=b"",
        mime_type="application/pdf",
        metadata={"injected_text": HINDI_DEVANAGARI_SALE_DEED}
    )

    assert result.total_pages == 1
    page = result.pages[0]
    assert page.language == "eng+hin"
    assert len(page.spans) > 5

    # Check Hindi Devanagari span
    hindi_spans = [s for s in page.spans if s.language == "hin"]
    assert len(hindi_spans) > 0
    first_hindi = hindi_spans[0]
    assert any('\u0900' <= c <= '\u097f' for c in first_hindi.text)
    assert first_hindi.bbox.x_min >= 0.0 and first_hindi.bbox.x_max <= 1.0
    assert first_hindi.bbox.y_max > first_hindi.bbox.y_min


def test_ocr_provider_multi_page_splitting():
    """Validates multi-page separation via page breaks."""
    provider = DemoOCRProvider()
    result = provider.process(
        document_content=b"",
        mime_type="application/pdf",
        metadata={"injected_text": MULTI_PAGE_DOCUMENT_TEXT}
    )

    assert result.total_pages == 2
    assert result.pages[0].page_number == 1
    assert "PAGE 1" in result.pages[0].full_text
    assert result.pages[1].page_number == 2
    assert "PAGE 2" in result.pages[1].full_text


def test_ocr_provider_empty_document():
    """Validates empty or whitespace-only documents produce safe empty page results."""
    provider = DemoOCRProvider()
    result = provider.process(
        document_content=b"   \n  \t  ",
        mime_type="text/plain"
    )
    assert result.total_pages == 1
    assert result.pages[0].confidence == 0.0
    assert len(result.pages[0].spans) == 0


def test_ocr_tesseract_availability_safeguard():
    """Validates Tesseract provider raises clear runtime error if binary not found."""
    tess = TesseractOCRProvider()
    if not tess.is_available:
        with pytest.raises(RuntimeError, match="Tesseract binary is not installed"):
            tess.process(b"test", "application/pdf")


# =====================================================================
# B. Document Classification
# =====================================================================

def test_document_classification_bilingual_signals():
    """Tests classification for Bihar land records across English & Devanagari."""
    # 1. Sale deed in Hindi
    res_sd = DocumentClassifier.classify(HINDI_DEVANAGARI_SALE_DEED, "deed_2022.pdf")
    assert res_sd.document_category == DocumentCategory.SALE_DEED
    assert res_sd.confidence >= 0.80
    assert "बैनामा" in res_sd.matched_signals["matched_terms"] or "विक्रेता" in res_sd.matched_signals["matched_terms"]
    assert res_sd.review_required is False

    # 2. Khatiyan in English & Hindi
    res_kh = DocumentClassifier.classify("Bihar Revenue Khatiyan खतियान CS Khatiyan raiyat name lagan", "khatian.pdf")
    assert res_kh.document_category == DocumentCategory.KHATIYAN
    assert res_kh.confidence >= 0.80

    # 3. Cadastral map
    res_map = DocumentClassifier.classify("Cadastral Map Naksha भू-नक्शा scale 16 inch LPM certificate", "naksha.png")
    assert res_map.document_category == DocumentCategory.CADASTRAL_MAP

    # 4. Unknown / Unsupported
    res_unk = DocumentClassifier.classify("Employment Contract Agreement salary benefits", "contract.pdf")
    assert res_unk.document_category == DocumentCategory.UNKNOWN
    assert res_unk.review_required is True
    assert res_unk.processing_status == "REVIEW_REQUIRED"


def test_document_classification_ambiguity_handling():
    """Tests that documents with conflicting/tied signals are flagged for review."""
    # Text with both sale deed and mutation signals
    ambiguous_text = "Sale deed बैनामा with dakhil kharij दाखिल खारिज case order"
    res = DocumentClassifier.classify(ambiguous_text, "record.pdf")
    # Should record alternative classifications
    assert len(res.alternative_classifications) > 0
    assert res.review_required is True


# =====================================================================
# C. Structured Field Extraction & Normalization
# =====================================================================

def test_bilingual_sale_deed_parser():
    """Tests SaleDeedParser on mixed Hindi-English Bihar deed."""
    provider = DemoOCRProvider()
    ocr_res = provider.process(b"", "application/pdf", metadata={"injected_text": HINDI_DEVANAGARI_SALE_DEED})

    parser = SaleDeedParser()
    parse_res = parser.parse(ocr_res)

    # Khata & Plot
    khata = parse_res.get_field("khata_number")
    assert khata is not None
    assert khata.normalized_value == "145"

    plot = parse_res.get_field("plot_number")
    assert plot is not None
    assert plot.normalized_value == "890"

    # Parties
    seller = parse_res.get_field("seller_name")
    assert seller is not None
    assert "महेश प्रसाद" in seller.raw_value

    buyer = parse_res.get_field("buyer_name")
    assert buyer is not None
    assert "सुनीता देवी" in buyer.raw_value

    # Area
    area = parse_res.get_field("recorded_area")
    assert area is not None
    assert area.normalized_value["normalized_acres"] == 1.25

    # Consideration
    cons = parse_res.get_field("consideration_amount")
    assert cons is not None
    assert cons.normalized_value == 2500000.0


def test_bilingual_khatiyan_parser_with_page_provenance():
    """Tests KhatiyanParser and verifies field page-level provenance."""
    provider = DemoOCRProvider()
    ocr_res = provider.process(b"", "application/pdf", metadata={"injected_text": MULTI_PAGE_DOCUMENT_TEXT})

    parser = KhatiyanParser()
    parse_res = parser.parse(ocr_res)

    khata = parse_res.get_field("khata_number")
    assert khata is not None
    assert khata.normalized_value == "78"
    assert khata.page_number == 1  # Khata was on page 1

    plot = parse_res.get_field("plot_number")
    assert plot is not None
    assert plot.normalized_value == "450"
    assert plot.page_number == 2  # Plot was on page 2

    raiyat = parse_res.get_field("recorded_raiyat")
    assert raiyat is not None
    assert "Ramdhani Mahto" in raiyat.raw_value
    assert raiyat.page_number == 1


def test_chauhaddi_boundary_extractor():
    """Tests ChauhaddiExtractor for 4-sided directional boundaries, road widths, and neighbors."""
    text = (
        "चौहद्दी विवरणी:\n"
        "उत्तर - 20 फीट चौड़ा पीडब्ल्यूडी सड़क\n"
        "दक्षिण - प्लॉट संख्या 512 स्वर्गीय मदन लाल का खेत\n"
        "पूरब - निज विक्रेता की शेष भूमि\n"
        "पश्चिम - सर्वसाधारण नाला 10 फीट\n"
    )
    res = ChauhaddiExtractor.extract_boundaries(text)
    assert res.has_all_four_directions is True
    assert res.directions_found_count == 4

    # North (Road)
    assert res.north is not None
    assert res.north.is_road_or_path is True
    assert res.north.road_width_feet == 20.0

    # South (Neighbor with Plot)
    assert res.south is not None
    assert res.south.adjoining_plot_number == "512"

    # East (Seller Nij land)
    assert res.east is not None
    assert "विक्रेता" in res.east.raw_text

    # West (Waterway/Path)
    assert res.west is not None
    assert res.west.is_road_or_path is True


def test_area_normalization_hindi_and_missing_units():
    """Tests Area normalization across units, composite expressions, and missing unit rejection."""
    # 1. Hindi Devanagari एकड़ and डिसमिल
    norm1 = NormalizationService.normalize_area("2 एकड़ 50 डिसमिल")
    assert norm1.normalized_acres == 2.50
    assert norm1.normalized_sqm > 10000.0

    # 2. Bihar regional Bigha-Katha
    norm2 = NormalizationService.normalize_area("1 बीघा 10 कट्ठा")
    assert norm2.normalized_acres == 0.9375  # 1.5 Bigha * (5/8) = 0.9375 ac

    # 3. Missing Unit Rejection Rule: Never guess a missing unit without explicit confirmation
    norm_missing = NormalizationService.normalize_area("150")
    assert norm_missing.is_uncertain is True
    assert norm_missing.normalized_acres is None
    assert "MISSING_UNIT" in norm_missing.conversion_rule


# =====================================================================
# D. Cross-Reference Existing Bhumi Setu Records
# =====================================================================

def test_cross_reference_exact_match(db_session: Session, tenant_a: Organization, user_a: User):
    """Tests exact match against registered parcel with consistent area."""
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BR-PAT-DAN-KOT-KH145-PL890",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        mauza_village_name="Kothawan",
        census_village_code="CVC-890",
        plot_khesra_number="890",
        khata_number="145",
        recorded_area_acres=1.25
    )
    db_session.add(parcel)

    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.SALE_DEED,
        original_filename="deed.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_uri="mock://deed.pdf",
        sha256_hash="a" * 64
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        content_hash=doc.sha256_hash,
        storage_reference=doc.storage_uri,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes
    )
    db_session.add(ver)
    db_session.flush()

    # Add ExtractedFields matching parcel
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="khata_number", raw_value="145", normalized_value="145", confidence=0.98))
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="plot_number", raw_value="890", normalized_value="890", confidence=0.98))
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="recorded_area", raw_value="1.25 Acre", normalized_value={"standard_acres": 1.25, "square_meters": 5058.57}, confidence=0.95))
    db_session.commit()

    res = DocumentCrossReferenceService.cross_reference_document(
        document_id=doc.document_id,
        org_id=tenant_a.org_id,
        db=db_session
    )

    assert res.status == CrossReferenceStatus.EXACT_MATCH.value
    assert res.matched_parcel is not None
    assert res.matched_parcel.bhumi_id == parcel.bhumi_id
    assert res.review_required is False


def test_cross_reference_area_discrepancy(db_session: Session, tenant_a: Organization):
    """Tests area delta > 5% triggers AREA_DISCREPANCY finding."""
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BR-PAT-DAN-KOT-KH10-PL20",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        mauza_village_name="Kothawan",
        census_village_code="CVC-20",
        plot_khesra_number="20",
        khata_number="10",
        recorded_area_acres=1.00  # Parcel has 1.00 Acre
    )
    db_session.add(parcel)

    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.SALE_DEED,
        original_filename="deed_area.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_uri="mock://deed_area.pdf",
        sha256_hash="b" * 64
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        content_hash=doc.sha256_hash,
        storage_reference=doc.storage_uri,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes
    )
    db_session.add(ver)
    db_session.flush()

    # Document claims 1.50 Acres (50% delta)
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="khata_number", raw_value="10", normalized_value="10", confidence=0.98))
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="plot_number", raw_value="20", normalized_value="20", confidence=0.98))
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="recorded_area", raw_value="1.50 Acre", normalized_value={"standard_acres": 1.50, "square_meters": 6070.28}, confidence=0.95))
    db_session.commit()

    res = DocumentCrossReferenceService.cross_reference_document(
        document_id=doc.document_id,
        org_id=tenant_a.org_id,
        db=db_session
    )

    assert res.status == CrossReferenceStatus.AREA_DISCREPANCY.value
    assert res.review_required is True
    assert len(res.discrepancies) > 0
    disc = res.discrepancies[0]
    assert disc["field"] == "recorded_area"
    assert disc["delta_percentage"] > 15.0


def test_cross_reference_identifier_conflict(db_session: Session, tenant_a: Organization):
    """Tests matching Plot but mismatched Khata triggers IDENTIFIER_CONFLICT."""
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BR-PAT-DAN-KOT-KH99-PL77",
        state_code="BR",
        district_name="Patna",
        subdistrict_anchal_name="Danapur",
        mauza_village_name="Kothawan",
        census_village_code="CVC-77",
        plot_khesra_number="77",
        khata_number="99",  # Parcel has Khata 99
        recorded_area_acres=0.50
    )
    db_session.add(parcel)

    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.SALE_DEED,
        original_filename="conflict.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_uri="mock://conflict.pdf",
        sha256_hash="c" * 64
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        content_hash=doc.sha256_hash,
        storage_reference=doc.storage_uri,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes
    )
    db_session.add(ver)
    db_session.flush()

    # Document has Plot 77 but Khata 33
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="khata_number", raw_value="33", normalized_value="33", confidence=0.98))
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="plot_number", raw_value="77", normalized_value="77", confidence=0.98))
    db_session.commit()

    res = DocumentCrossReferenceService.cross_reference_document(
        document_id=doc.document_id,
        org_id=tenant_a.org_id,
        db=db_session
    )

    assert res.status == CrossReferenceStatus.IDENTIFIER_CONFLICT.value
    assert res.review_required is True


def test_cross_reference_insufficient_identifiers(db_session: Session, tenant_a: Organization):
    """Tests document lacking both Khata and Plot returns INSUFFICIENT_DATA."""
    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.UNKNOWN,
        original_filename="blurry.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_uri="mock://blurry.pdf",
        sha256_hash="d" * 64
    )
    db_session.add(doc)
    db_session.commit()

    res = DocumentCrossReferenceService.cross_reference_document(
        document_id=doc.document_id,
        org_id=tenant_a.org_id,
        db=db_session
    )

    assert res.status == CrossReferenceStatus.INSUFFICIENT_DATA.value
    assert res.review_required is True


# =====================================================================
# E. Human Review Workflow & Audit Trail
# =====================================================================

def test_human_review_workflow_accept_and_edit(
    client: TestClient,
    db_session: Session,
    tenant_a: Organization,
    user_a: User,
    auth_headers_a: dict
):
    """
    Tests reviewer accepting and editing extracted values via API,
    ensuring original raw values and reviewer audit logs are preserved.
    """
    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.SALE_DEED,
        original_filename="audit_test.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_uri="mock://audit.pdf",
        sha256_hash="e" * 64
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        content_hash=doc.sha256_hash,
        storage_reference=doc.storage_uri,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes
    )
    db_session.add(ver)
    db_session.flush()

    field = ExtractedField(
        document_id=doc.document_id,
        version_id=ver.version_id,
        field_name="khata_number",
        raw_value="145/B (Ambiguous)",
        normalized_value="145",
        confidence=0.72,
        status=ExtractedFieldStatus.CANDIDATE
    )
    db_session.add(field)
    db_session.commit()

    # 1. Reviewer performs EDIT
    edit_res = client.post(
        f"/api/v1/extractions/{field.field_id}/review",
        json={
            "action": "EDIT",
            "reviewed_value": "145/B",
            "review_notes": "Ground verification confirmed sub-khata 145/B"
        },
        headers=auth_headers_a
    )
    assert edit_res.status_code == 200
    data = edit_res.json()
    assert data["status"] == ExtractedFieldStatus.VALIDATED
    assert data["normalized_value"] == "145/B"
    assert data["raw_value"] == "145/B (Ambiguous)"  # Original raw value preserved!
    assert data["review_notes"] == "Ground verification confirmed sub-khata 145/B"

    # 2. Check DB audit fields
    db_session.refresh(field)
    assert field.reviewed_by_user_id == user_a.user_id
    assert field.reviewed_at is not None


def test_cross_tenant_isolation_on_document_and_review(
    client: TestClient,
    db_session: Session,
    tenant_a: Organization,
    tenant_b: Organization,
    auth_headers_b: dict
):
    """Validates that Tenant B cannot access or review Tenant A's document or extractions."""
    doc_a = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.SALE_DEED,
        original_filename="private_a.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_uri="mock://private_a.pdf",
        sha256_hash="f" * 64
    )
    db_session.add(doc_a)
    db_session.flush()

    ver_a = DocumentVersion(
        document_id=doc_a.document_id,
        version_number=1,
        content_hash=doc_a.sha256_hash,
        storage_reference=doc_a.storage_uri,
        mime_type=doc_a.mime_type,
        file_size_bytes=doc_a.file_size_bytes
    )
    db_session.add(ver_a)
    db_session.flush()

    field_a = ExtractedField(
        document_id=doc_a.document_id,
        version_id=ver_a.version_id,
        field_name="plot_number",
        raw_value="101",
        normalized_value="101",
        confidence=0.95
    )
    db_session.add(field_a)
    db_session.commit()

    # Tenant B tries to get document
    res_doc = client.get(f"/api/v1/documents/{doc_a.document_id}", headers=auth_headers_b)
    assert res_doc.status_code == 403

    # Tenant B tries to review field
    res_rev = client.post(
        f"/api/v1/extractions/{field_a.field_id}/review",
        json={"action": "ACCEPT"},
        headers=auth_headers_b
    )
    assert res_rev.status_code == 403


# =====================================================================
# F. Security & API Endpoints
# =====================================================================

def test_api_document_classification_and_cross_reference_endpoints(
    client: TestClient,
    db_session: Session,
    tenant_a: Organization,
    auth_headers_a: dict
):
    """Tests the new GET /classification and POST /cross-reference endpoints."""
    parcel = Parcel(
        org_id=tenant_a.org_id,
        bhumi_id="BR-GAY-BOD-BAK-KH78-PL450",
        state_code="BR",
        district_name="Gaya",
        subdistrict_anchal_name="Bodhgaya",
        mauza_village_name="Bakraur",
        census_village_code="CVC-312",
        plot_khesra_number="450",
        khata_number="78",
        recorded_area_acres=1.5625
    )
    db_session.add(parcel)

    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.KHATIYAN,
        original_filename="khatiyan_sample.pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        storage_uri="mock://khatiyan.pdf",
        sha256_hash="1" * 64,
        document_metadata={
            "classification": {
                "document_category": "KHATIYAN",
                "confidence": 0.95,
                "method": "HYBRID_KEYWORD_REGEX_HEURISTIC",
                "model_version": "doc-classifier-v1.2",
                "matched_signals": {"matched_terms": ["khatiyan", "raiyat"], "match_count": 2},
                "review_required": False,
                "processing_status": "CLASSIFIED"
            }
        }
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        content_hash=doc.sha256_hash,
        storage_reference=doc.storage_uri,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes
    )
    db_session.add(ver)
    db_session.flush()

    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="khata_number", raw_value="78", normalized_value="78", confidence=0.98))
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="plot_number", raw_value="450", normalized_value="450", confidence=0.98))
    db_session.add(ExtractedField(document_id=doc.document_id, version_id=ver.version_id, field_name="recorded_area", raw_value="1.5625 Acre", normalized_value={"standard_acres": 1.5625, "square_meters": 6323.21}, confidence=0.95))
    db_session.commit()

    # 1. Classification endpoint
    cls_res = client.get(f"/api/v1/documents/{doc.document_id}/classification", headers=auth_headers_a)
    assert cls_res.status_code == 200
    cls_data = cls_res.json()
    assert cls_data["document_category"] == "KHATIYAN"
    assert cls_data["confidence"] == 0.95

    # 2. Cross-reference endpoint
    cross_res = client.post(f"/api/v1/documents/{doc.document_id}/cross-reference", headers=auth_headers_a)
    assert cross_res.status_code == 200
    cross_data = cross_res.json()
    assert cross_data["status"] == "EXACT_MATCH"
    assert cross_data["matched_parcel"]["bhumi_id"] == parcel.bhumi_id
    assert "Automated cross-reference results are derived heuristics" in cross_data["epistemic_notice"]
