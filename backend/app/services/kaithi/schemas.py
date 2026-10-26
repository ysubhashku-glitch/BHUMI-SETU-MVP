"""
Pydantic Schemas for Structured Kaithi Script Vision Recognition Results,
Coordinate Provenance, and Human Review Corrections.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

EPISTEMIC_KAITHI_DISCLAIMER = (
    "NOTICE: Kaithi historical script OCR is an automated probabilistic reading "
    "of pre-digitization revenue records. It does NOT constitute legal proof of title, "
    "certified judicial record, or authoritative boundary demarcation. All low-confidence "
    "readings require verification by an authorized Revenue Officer or LandAmin."
)

class KaithiBoundingBox(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    model_config = ConfigDict(from_attributes=True)


class KaithiGlyphCandidate(BaseModel):
    character: str
    codepoint: str
    devanagari: str
    confidence: float


class KaithiGlyphPrediction(BaseModel):
    glyph_index: int
    character: str
    codepoint: str
    devanagari: str
    iast: str
    confidence: float
    bbox: KaithiBoundingBox
    alternative_candidates: List[KaithiGlyphCandidate] = []

    model_config = ConfigDict(from_attributes=True)


class KaithiLinePrediction(BaseModel):
    line_number: int
    raw_kaithi_text: str
    devanagari_text: str
    iast_text: str
    confidence: float
    bbox: KaithiBoundingBox
    region_type: str = "TEXT_LINE"  # HEADER, TABULAR_ROW, MARGIN
    review_required: bool = False
    uncertainty_reasons: List[str] = []
    glyphs: List[KaithiGlyphPrediction] = []

    model_config = ConfigDict(from_attributes=True)


class KaithiPagePrediction(BaseModel):
    page_number: int
    full_kaithi_text: str
    full_devanagari_text: str
    full_iast_text: str
    page_confidence: float
    review_required: bool = False
    lines: List[KaithiLinePrediction] = []

    model_config = ConfigDict(from_attributes=True)


class KaithiRecognitionResult(BaseModel):
    document_id: Optional[str] = None
    version_id: Optional[str] = None
    ocr_engine: str = "KAITHI_VISION_ENGINE"
    ocr_version: str = "1.0.0-bhumisetu"
    script: str = "KAITHI"
    script_confidence: float = 0.95
    mean_confidence: float
    review_required: bool
    uncertainty_flags: List[str] = []
    pages: List[KaithiPagePrediction] = []
    preprocessing_summary: Dict[str, Any] = {}
    lexicon_matches: List[Dict[str, Any]] = []
    processing_duration_sec: float
    epistemic_notice: str = EPISTEMIC_KAITHI_DISCLAIMER

    model_config = ConfigDict(from_attributes=True)


class KaithiReviewItem(BaseModel):
    line_number: int
    original_raw_text: str
    corrected_text: str
    review_notes: Optional[str] = None


class KaithiReviewRequest(BaseModel):
    document_id: str
    version_id: Optional[str] = None
    corrections: List[KaithiReviewItem]
    reviewer_notes: Optional[str] = None


class KaithiReviewResponse(BaseModel):
    document_id: str
    version_id: str
    status: str  # REVIEWED, PARTIALLY_REVIEWED
    total_corrections: int
    reviewed_at: datetime
    reviewed_by_user_id: Optional[str] = None
    review_summary: List[Dict[str, Any]] = []
    epistemic_notice: str = EPISTEMIC_KAITHI_DISCLAIMER

    model_config = ConfigDict(from_attributes=True)
