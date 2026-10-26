"""
Kaithi Vision Recognition and Historical Script Processing Package
"""

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
    SegmentationResult,
    SegmentedLineRegion,
    SegmentedGlyphRegion,
    SegmentedBoundingBox
)
from app.services.kaithi.schemas import (
    KaithiBoundingBox,
    KaithiGlyphCandidate,
    KaithiGlyphPrediction,
    KaithiLinePrediction,
    KaithiPagePrediction,
    KaithiRecognitionResult,
    KaithiReviewItem,
    KaithiReviewRequest,
    KaithiReviewResponse,
    EPISTEMIC_KAITHI_DISCLAIMER
)
from app.services.kaithi.engine import (
    TransliterationService,
    KaithiRecognitionEngine,
    BaselineKaithiEngine,
    ExternalKaithiEngineAdapter,
    get_kaithi_engine
)
from app.services.kaithi.evaluator import (
    KaithiEvaluator,
    levenshtein_distance
)

__all__ = [
    "KAITHI_CHARACTER_MAP",
    "DEV_TO_KAITHI",
    "BIHAR_REVENUE_LEXICON",
    "KAITHI_CONFUSION_PAIRS",
    "KaithiImagePreprocessor",
    "PreprocessedImageResult",
    "PreprocessingError",
    "KaithiDocumentSegmenter",
    "SegmentationResult",
    "SegmentedLineRegion",
    "SegmentedGlyphRegion",
    "SegmentedBoundingBox",
    "KaithiBoundingBox",
    "KaithiGlyphCandidate",
    "KaithiGlyphPrediction",
    "KaithiLinePrediction",
    "KaithiPagePrediction",
    "KaithiRecognitionResult",
    "KaithiReviewItem",
    "KaithiReviewRequest",
    "KaithiReviewResponse",
    "EPISTEMIC_KAITHI_DISCLAIMER",
    "TransliterationService",
    "KaithiRecognitionEngine",
    "BaselineKaithiEngine",
    "ExternalKaithiEngineAdapter",
    "get_kaithi_engine",
    "KaithiEvaluator",
    "levenshtein_distance",
]
