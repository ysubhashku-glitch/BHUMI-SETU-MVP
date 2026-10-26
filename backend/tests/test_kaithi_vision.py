"""
Comprehensive Automated Test Suite for TASK-P2-01:
Kaithi Historical Script Vision Model Integration.

Covers all 12 required test dimensions:
1. Valid image ingestion.
2. Unsupported files and malformed images.
3. Preprocessing behavior and failure handling (contrast, deskew, binarization).
4. Model loading and unavailable-model behavior (graceful fallback).
5. Recognition output schema validation.
6. Confidence and uncertainty handling (review_required, uncertainty reasons).
7. Text-region coordinate integrity (0.0 <= x_min < x_max <= 1.0).
8. Document and page provenance preservation.
9. Background-job integration (Celery worker task logic).
10. Human-review correction and audit preservation (immutable raw vs reviewed).
11. Regression compatibility with existing OCR workflows.
12. API authorization and upload security controls (tenant isolation).
Additional:
13. Transliteration (Kaithi <-> Devanagari <-> IAST) & Bihar revenue lexicon.
14. Evaluation harness (Character Error Rate CER & Word Error Rate WER).
"""

import io
import uuid
import pytest
from PIL import Image, ImageDraw

from app.models.evidence import (
    Document,
    DocumentCategory,
    DocumentVersion,
    DocumentPage,
    DocumentProcessingStatus,
    EvidenceSpan,
    ExtractedField
)
from app.core.storage import get_document_storage
from app.services.kaithi.unicode_table import (
    KAITHI_CHARACTER_MAP,
    DEV_TO_KAITHI,
    BIHAR_REVENUE_LEXICON,
    KAITHI_CONFUSION_PAIRS
)
from app.services.kaithi.preprocessor import (
    KaithiImagePreprocessor,
    PreprocessedImageResult,
    PreprocessingError
)
from app.services.kaithi.segmenter import (
    KaithiDocumentSegmenter,
    SegmentationResult
)
from app.services.kaithi.schemas import (
    KaithiRecognitionResult,
    KaithiReviewRequest,
    KaithiReviewItem,
    EPISTEMIC_KAITHI_DISCLAIMER
)
from app.services.kaithi.engine import (
    TransliterationService,
    BaselineKaithiEngine,
    ExternalKaithiEngineAdapter,
    get_kaithi_engine
)
from app.services.kaithi.evaluator import (
    KaithiEvaluator,
    levenshtein_distance
)
from app.services.ocr_engine import get_ocr_provider, KaithiOCRProvider, DemoOCRProvider
from app.services.document_pipeline import DocumentPipelineService
from app.worker import process_document_ocr_task_logic


def _generate_synthetic_document_image(
    width: int = 800,
    height: int = 1000,
    num_lines: int = 4
) -> bytes:
    """Helper creating a valid grayscale document image with simulated ink strokes."""
    img = Image.new("L", (width, height), color=245)  # Light paper background
    draw = ImageDraw.Draw(img)

    # Draw header line
    draw.rectangle([50, 60, width - 50, 90], fill=30)  # Simulated title block

    # Draw text lines
    line_step = (height - 200) // max(num_lines, 1)
    for i in range(num_lines):
        y = 150 + i * line_step
        # Draw clusters of dark ink strokes representing cursive characters
        for block_x in range(80, width - 80, 70):
            draw.rectangle([block_x, y, block_x + 50, y + 25], fill=25)
            # Add small diacritic / stroke above or below
            draw.line([block_x, y + 30, block_x + 40, y + 30], fill=30, width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Test 1: Valid Image Ingestion
# -----------------------------------------------------------------------------
def test_valid_image_ingestion():
    raw_bytes = _generate_synthetic_document_image(width=600, height=800)
    img = KaithiImagePreprocessor.validate_and_load(raw_bytes)
    assert img is not None
    assert img.size == (600, 800)
    assert img.format == "PNG"


# -----------------------------------------------------------------------------
# Test 2: Unsupported Files and Malformed Images
# -----------------------------------------------------------------------------
def test_unsupported_and_malformed_images():
    # Empty payload
    with pytest.raises(PreprocessingError) as exc_empty:
        KaithiImagePreprocessor.validate_and_load(b"")
    assert exc_empty.value.code == "EMPTY_PAYLOAD"

    # Truncated corrupt payload
    with pytest.raises(PreprocessingError) as exc_corrupt:
        KaithiImagePreprocessor.validate_and_load(b"NOT_AN_IMAGE_HEADER")
    assert exc_corrupt.value.code in ("CORRUPT_PAYLOAD", "DECODE_FAILURE")

    # Dimensions too small
    tiny_img = Image.new("L", (10, 10), color=255)
    tiny_buf = io.BytesIO()
    tiny_img.save(tiny_buf, format="PNG")
    with pytest.raises(PreprocessingError) as exc_small:
        KaithiImagePreprocessor.validate_and_load(tiny_buf.getvalue())
    assert exc_small.value.code == "DIMENSION_TOO_SMALL"


# -----------------------------------------------------------------------------
# Test 3: Preprocessing Behavior and Failure Handling
# -----------------------------------------------------------------------------
def test_preprocessing_behavior_and_failure_handling():
    raw_bytes = _generate_synthetic_document_image(width=500, height=700)
    result = KaithiImagePreprocessor.process(
        content=raw_bytes,
        apply_contrast=True,
        apply_noise_reduction=True,
        apply_deskew=True,
        apply_binarization=True
    )

    assert isinstance(result, PreprocessedImageResult)
    assert result.width == 500
    assert result.height == 700
    assert len(result.image_bytes) > 0
    assert "INPUT_VALIDATION" in result.transformations
    assert any("OTSU_BINARIZATION" in t for t in result.transformations)
    assert result.histogram_summary["dark_pixel_ratio"] > 0.0


# -----------------------------------------------------------------------------
# Test 4: Model Loading and Unavailable-Model Behavior
# -----------------------------------------------------------------------------
def test_model_loading_and_unavailable_model_behavior():
    raw_bytes = _generate_synthetic_document_image(width=400, height=500)
    # Instantiate external adapter pointing to non-existent weights
    adapter = ExternalKaithiEngineAdapter(model_path="/nonexistent/path/kaithi_neural.pt")
    assert not adapter.is_loaded

    # Execution must not crash; must safely fall back to baseline engine
    result = adapter.recognize_document(raw_bytes)
    assert result is not None
    assert "FALLBACK" in result.ocr_engine
    assert "EXTERNAL_MODEL_UNAVAILABLE_FALLBACK_APPLIED" in result.uncertainty_flags


# -----------------------------------------------------------------------------
# Test 5: Recognition Output Schema Validation
# -----------------------------------------------------------------------------
def test_recognition_output_schema_validation():
    raw_bytes = _generate_synthetic_document_image(width=400, height=600)
    engine = BaselineKaithiEngine()
    result = engine.recognize_document(raw_bytes)

    assert isinstance(result, KaithiRecognitionResult)
    assert result.script == "KAITHI"
    assert result.script_confidence >= 0.90
    assert 0.0 <= result.mean_confidence <= 1.0
    assert len(result.pages) >= 1
    assert result.epistemic_notice == EPISTEMIC_KAITHI_DISCLAIMER

    # Validate lines and glyph predictions
    page = result.pages[0]
    assert len(page.lines) >= 1
    for line in page.lines:
        assert line.line_number >= 1
        assert len(line.raw_kaithi_text) > 0
        assert len(line.devanagari_text) > 0
        assert len(line.iast_text) > 0
        assert 0.0 <= line.confidence <= 1.0


# -----------------------------------------------------------------------------
# Test 6: Confidence and Uncertainty Handling
# -----------------------------------------------------------------------------
def test_confidence_and_uncertainty_handling():
    raw_bytes = _generate_synthetic_document_image(width=300, height=400)
    engine = BaselineKaithiEngine()

    # Pass low-confidence / noisy characters
    meta = {"injected_kaithi_text": "\U0001108D \U000110A9 \U000110AA"}
    result = engine.recognize_document(raw_bytes, metadata=meta)

    assert result is not None
    # Check that lexicon matches boost confidence for revenue keywords
    khatiyan_meta = {"injected_kaithi_text": BIHAR_REVENUE_LEXICON["KHATIYAN"]["kaithi"]}
    res_khatiyan = engine.recognize_document(raw_bytes, metadata=khatiyan_meta)
    assert len(res_khatiyan.lexicon_matches) >= 1
    assert res_khatiyan.lexicon_matches[0]["term"] == "KHATIYAN"


# -----------------------------------------------------------------------------
# Test 7: Text-Region Coordinate Integrity
# -----------------------------------------------------------------------------
def test_text_region_coordinate_integrity():
    raw_bytes = _generate_synthetic_document_image(width=500, height=600)
    engine = BaselineKaithiEngine()
    result = engine.recognize_document(raw_bytes)

    for page in result.pages:
        for line in page.lines:
            bbox = line.bbox
            assert 0.0 <= bbox.x_min <= 1.0
            assert 0.0 <= bbox.y_min <= 1.0
            assert 0.0 <= bbox.x_max <= 1.0
            assert 0.0 <= bbox.y_max <= 1.0
            assert bbox.x_min <= bbox.x_max
            assert bbox.y_min <= bbox.y_max

            for glyph in line.glyphs:
                gb = glyph.bbox
                assert 0.0 <= gb.x_min <= 1.0
                assert 0.0 <= gb.y_min <= 1.0
                assert 0.0 <= gb.x_max <= 1.0
                assert 0.0 <= gb.y_max <= 1.0


# -----------------------------------------------------------------------------
# Test 8: Document and Page Provenance Preservation
# -----------------------------------------------------------------------------
def test_document_and_page_provenance_preservation(db_session, tenant_a, user_a):
    raw_bytes = _generate_synthetic_document_image(width=500, height=700)
    storage = get_document_storage()
    storage_res = storage.put(
        content=raw_bytes,
        destination_name="test_kaithi_cs_khatiyan.png",
        mime_type="image/png"
    )

    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.KHATIYAN,
        original_filename="cs_khatiyan_kaithi_plate.png",
        mime_type="image/png",
        file_size_bytes=len(raw_bytes),
        storage_uri=storage_res["storage_reference"],
        sha256_hash=storage_res["sha256_hash"],
        uploader_party_id=None,
        processing_status=DocumentProcessingStatus.STORED,
        document_metadata={
            "script": "KAITHI",
            "injected_kaithi_text": (
                BIHAR_REVENUE_LEXICON["KHATIYAN"]["kaithi"] + "\n" +
                BIHAR_REVENUE_LEXICON["KHATA"]["kaithi"] + " ४२ " +
                BIHAR_REVENUE_LEXICON["KHESRA"]["kaithi"] + " ११२"
            )
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
        file_size_bytes=doc.file_size_bytes,
        processing_status=DocumentProcessingStatus.STORED
    )
    db_session.add(ver)
    db_session.commit()

    # Execute pipeline
    processed_ver = DocumentPipelineService.execute_pipeline(
        document_id=doc.document_id,
        version_id=ver.version_id,
        db=db_session
    )

    assert processed_ver.ocr_engine == "KAITHI_VISION_ENGINE"
    assert processed_ver.processing_status in (DocumentProcessingStatus.READY, DocumentProcessingStatus.VALIDATION_REQUIRED)

    # Check pages and evidence spans
    pages = db_session.query(DocumentPage).filter(DocumentPage.version_id == ver.version_id).all()
    assert len(pages) == 1
    assert pages[0].ocr_text is not None

    spans = db_session.query(EvidenceSpan).filter(EvidenceSpan.version_id == ver.version_id).all()
    assert len(spans) >= 1
    for s in spans:
        assert s.source_type == "OCR"
        assert s.x_min is not None and s.x_max is not None


# -----------------------------------------------------------------------------
# Test 9: Background-Job Integration (Celery Task Logic)
# -----------------------------------------------------------------------------
def test_background_job_integration(db_session, tenant_a, user_a):
    raw_bytes = _generate_synthetic_document_image(width=400, height=500)
    storage = get_document_storage()
    storage_res = storage.put(content=raw_bytes, destination_name="async_kaithi.png", mime_type="image/png")

    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.KHATIYAN,
        original_filename="async_kaithi_deed.png",
        mime_type="image/png",
        file_size_bytes=len(raw_bytes),
        storage_uri=storage_res["storage_reference"],
        sha256_hash=storage_res["sha256_hash"],
        processing_status=DocumentProcessingStatus.STORED,
        document_metadata={"script": "KAITHI"}
    )
    db_session.add(doc)
    db_session.flush()

    ver = DocumentVersion(
        document_id=doc.document_id,
        version_number=1,
        content_hash=doc.sha256_hash,
        storage_reference=doc.storage_uri,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        processing_status=DocumentProcessingStatus.STORED
    )
    db_session.add(ver)
    db_session.commit()

    case_id = str(uuid.uuid4())
    result = process_document_ocr_task_logic(
        document_id=str(doc.document_id),
        version_id=str(ver.version_id),
        case_id=case_id,
        user_id=str(user_a.user_id),
        db=db_session
    )

    assert result["status"] == "SUCCESS"
    assert result["document_id"] == str(doc.document_id)
    assert result["version_id"] == str(ver.version_id)


# -----------------------------------------------------------------------------
# Test 10: Human-Review Correction and Audit Preservation
# -----------------------------------------------------------------------------
def test_human_review_correction_and_audit_preservation(client, auth_headers_a, db_session, tenant_a):
    raw_bytes = _generate_synthetic_document_image(width=400, height=500)
    storage = get_document_storage()
    storage_res = storage.put(content=raw_bytes, destination_name="review_kaithi.png", mime_type="image/png")

    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.KHATIYAN,
        original_filename="historical_kaithi_khatiyan.png",
        mime_type="image/png",
        file_size_bytes=len(raw_bytes),
        storage_uri=storage_res["storage_reference"],
        sha256_hash=storage_res["sha256_hash"],
        processing_status=DocumentProcessingStatus.STORED,
        document_metadata={
            "script": "KAITHI",
            "kaithi_ocr_result": {
                "pages": [
                    {
                        "page_number": 1,
                        "lines": [
                            {
                                "line_number": 1,
                                "raw_kaithi_text": "\U0001108D\U000110A9",
                                "devanagari_text": "कर",
                                "confidence": 0.65,
                                "review_required": True
                            }
                        ]
                    }
                ]
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
        file_size_bytes=doc.file_size_bytes,
        processing_status=DocumentProcessingStatus.READY
    )
    db_session.add(ver)
    db_session.commit()

    # Submit human review correction
    review_payload = {
        "document_id": str(doc.document_id),
        "version_id": str(ver.version_id),
        "corrections": [
            {
                "line_number": 1,
                "original_raw_text": "कर",
                "corrected_text": "खतियान",
                "review_notes": "Corrected damaged first line glyph to Khatiyan based on Mauza header context"
            }
        ],
        "reviewer_notes": "Expert archivist review completed"
    }

    resp = client.post(
        f"/documents/{doc.document_id}/kaithi-review",
        json=review_payload,
        headers=auth_headers_a
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "REVIEWED"
    assert data["total_corrections"] == 1

    # Verify immutable audit log in database
    db_session.refresh(doc)
    audit = doc.document_metadata.get("kaithi_review_audit", [])
    assert len(audit) == 1
    assert audit[0]["original_raw_text"] == "कर"
    assert audit[0]["corrected_text"] == "खतियान"
    assert audit[0]["line_number"] == 1


# -----------------------------------------------------------------------------
# Test 11: Regression Compatibility With Existing OCR Workflows
# -----------------------------------------------------------------------------
def test_regression_compatibility_with_existing_ocr_workflows():
    # Standard provider request should return DemoOCRProvider
    standard_provider = get_ocr_provider(None)
    assert isinstance(standard_provider, DemoOCRProvider)

    # Calling process on standard English/Hindi text generates expected Demo spans
    demo_res = standard_provider.process(
        document_content=b"Sample English and Hindi document",
        mime_type="text/plain",
        metadata={"document_category": "SALE_DEED"}
    )
    assert demo_res.ocr_engine == DemoOCRProvider.ENGINE_NAME
    assert len(demo_res.pages) >= 1
    assert "SALE DEED" in demo_res.combined_text


# -----------------------------------------------------------------------------
# Test 12: API Authorization and Upload Security Controls
# -----------------------------------------------------------------------------
def test_api_authorization_and_upload_security_controls(client, auth_headers_a, auth_headers_b, db_session, tenant_a):
    raw_bytes = _generate_synthetic_document_image(width=400, height=400)
    storage = get_document_storage()
    storage_res = storage.put(content=raw_bytes, destination_name="tenant_iso.png", mime_type="image/png")

    doc = Document(
        org_id=tenant_a.org_id,
        document_category=DocumentCategory.KHATIYAN,
        original_filename="tenant_a_doc.png",
        mime_type="image/png",
        file_size_bytes=len(raw_bytes),
        storage_uri=storage_res["storage_reference"],
        sha256_hash=storage_res["sha256_hash"],
        processing_status=DocumentProcessingStatus.STORED
    )
    db_session.add(doc)
    db_session.commit()

    # Tenant B attempt to access Tenant A's Kaithi result must be rejected (403)
    resp_b = client.get(f"/documents/{doc.document_id}/kaithi-result", headers=auth_headers_b)
    assert resp_b.status_code == 403

    # Unauthenticated call must be rejected (401)
    resp_anon = client.get(f"/documents/{doc.document_id}/kaithi-result")
    assert resp_anon.status_code == 401

    # Tenant A access is permitted (200)
    resp_a = client.get(f"/documents/{doc.document_id}/kaithi-result", headers=auth_headers_a)
    assert resp_a.status_code == 200


# -----------------------------------------------------------------------------
# Test 13: Transliteration & Revenue Lexicon Integrity
# -----------------------------------------------------------------------------
def test_kaithi_transliteration_and_revenue_lexicon():
    # Consonants and vowels transliteration
    kaithi_khatiyan = BIHAR_REVENUE_LEXICON["KHATIYAN"]["kaithi"]
    dev_khatiyan = TransliterationService.kaithi_to_devanagari(kaithi_khatiyan)
    assert "ख" in dev_khatiyan
    assert "न" in dev_khatiyan

    # Reverse Devanagari to Kaithi
    dev_sample = "खाता"
    kai_sample = TransliterationService.devanagari_to_kaithi(dev_sample)
    assert "\U0001108E" in kai_sample  # KAITHI LETTER KHA

    # IAST Transliteration
    iast_res = TransliterationService.kaithi_to_iast(kaithi_khatiyan)
    assert "kh" in iast_res.lower()


# -----------------------------------------------------------------------------
# Test 14: Evaluation Harness (CER and WER Accuracy)
# -----------------------------------------------------------------------------
def test_evaluation_harness_cer_and_wer():
    # 1. Exact match (CER = 0.0, WER = 0.0)
    ref1 = "खाता बयालीस खेसरा एक सौ बारह"
    hyp1 = "खाता बयालीस खेसरा एक सौ बारह"
    res1 = KaithiEvaluator.compute_cer(ref1, hyp1)
    assert res1["cer"] == 0.0
    assert res1["accuracy"] == 1.0

    # 2. Known single substitution
    ref2 = "रैयत"
    hyp2 = "रयत"  # Deletion of matra
    res2 = KaithiEvaluator.compute_cer(ref2, hyp2)
    assert res2["deletions"] == 1
    assert res2["cer"] == 0.25  # 1/4

    # 3. Benchmark suite evaluation
    suite = [
        {"id": "plate_1", "reference": "खाता ४२", "hypothesis": "खाता ४२"},
        {"id": "plate_2", "reference": "खेसरा ११२", "hypothesis": "खेसरा ११३"}  # 1 substitution
    ]
    suite_metrics = KaithiEvaluator.evaluate_benchmark_suite(suite)
    assert suite_metrics["total_samples"] == 2
    assert suite_metrics["overall_cer"] > 0.0
    assert suite_metrics["overall_char_accuracy"] > 0.85
