import re
from typing import Dict, Any, Tuple
from app.models.evidence import DocumentCategory

class ClassificationResult:
    def __init__(
        self,
        document_category: str,
        confidence: float,
        method: str,
        model_version: str,
        matched_signals: Dict[str, Any],
        alternative_classifications: Optional[List[Dict[str, Any]]] = None,
        review_required: bool = False,
        processing_status: str = "CLASSIFIED"
    ):
        self.document_category = document_category
        self.confidence = round(confidence, 2)
        self.method = method
        self.model_version = model_version
        self.matched_signals = matched_signals
        self.alternative_classifications = alternative_classifications or []
        self.review_required = review_required
        self.processing_status = processing_status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_category": self.document_category,
            "confidence": self.confidence,
            "method": self.method,
            "model_version": self.model_version,
            "matched_signals": self.matched_signals,
            "alternative_classifications": self.alternative_classifications,
            "review_required": self.review_required,
            "processing_status": self.processing_status
        }

class DocumentClassifier:
    """
    Production candidate document classifier.
    Examines OCR text, filenames, and revenue vocabulary signals to categorize documents.
    Low-confidence classifications are classified as UNKNOWN to prevent silent failures.
    """
    MODEL_VERSION = "doc-classifier-v1.2"

    # Category signal dictionaries
    CATEGORY_PATTERNS = {
        DocumentCategory.SALE_DEED: [
            r"sale\s*deed", r"बैनामा", r"विक्रय\s*पत्र", r"deed\s*of\s*sale",
            r"kewala", r"केवाला", r"consideration\s*(?:money|amount|rs)", r"seller", r"विक्रेता",
            r"क्रेता", r"purchaser", r"दस्तावेज़\s*संख्या"
        ],
        DocumentCategory.GIFT_DEED: [
            r"gift\s*deed", r"दान\s*पत्र", r"hiba\s*nama", r"हिबानामा", r"deed\s*of\s*gift"
        ],
        DocumentCategory.PARTITION_DEED: [
            r"partition\s*deed", r"बंटवारा\s*नामा", r"takseem\s*nama", r"family\s*settlement\s*deed"
        ],
        DocumentCategory.MUTATION_RECORD: [
            r"dakhil\s*kharij", r"दाखिल\s*खारिज", r"mutation\s*(?:order|slip|case)",
            r"शुद्धि\s*पत्र", r"shuddhi\s*patra", r"circle\s*officer.*order", r"दाखिल-खारिज"
        ],
        DocumentCategory.KHATIYAN: [
            r"khatiyan", r"खतियान", r"raiyat\s*name", r"रैयतदार", r"cs\s*khatiyan", r"rs\s*khatiyan",
            r"thana\s*no", r"annual\s*rent", r"dhani\s*[1-3]", r"lagan", r"रैयत\s*का\s*नाम", r"किस्म\s*जमीन"
        ],
        DocumentCategory.JAMABANDI: [
            r"jamabandi", r"जमाबंदी", r"register\s*ii", r"पंजी\s*ii", r"halka", r"halka\s*no",
            r"demand\s*register", r"vol(?:ume)?\s*no.*page\s*no", r"जमाबंदी\s*पंजी"
        ],
        DocumentCategory.ENCUMBRANCE_CERTIFICATE: [
            r"encumbrance\s*certificate", r"non[- ]encumbrance", r"निरीक्षण\s*प्रमाण\s*पत्र",
            r"search\s*period", r"nil\s*encumbrance", r"form\s*no\s*15", r"form\s*no\s*16"
        ],
        DocumentCategory.CADASTRAL_MAP: [
            r"cadastral\s*map", r"naksha", r"नक्शा", r"plot\s*boundary\s*map", r"scale\s*16\s*inch",
            r"bhu[- ]?naksha", r"भू[- ]?नक्शा", r"lpm\s*certificate", r"भू-चित्र"
        ],
        DocumentCategory.IDENTITY_DOCUMENT: [
            r"aadhar", r"aadhaar", r"pan\s*card", r"election\s*commission", r"voter\s*id",
            r"passport\s*of\s*india"
        ]
    }

    @classmethod
    def classify(
        cls,
        text: str,
        filename: str = "",
        minimum_confidence: float = 0.60
    ) -> ClassificationResult:
        normalized_text = (text + " " + filename).lower()
        scored_candidates = []

        for category, patterns in cls.CATEGORY_PATTERNS.items():
            category_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, normalized_text, re.IGNORECASE)
                if matches:
                    category_matches.extend(matches)
            
            score = len(category_matches)
            if score > 0:
                if score >= 3:
                    cat_conf = min(0.70 + (score * 0.05), 0.98)
                elif score == 2:
                    cat_conf = 0.75
                else:
                    cat_conf = 0.62
                scored_candidates.append({
                    "category": category,
                    "score": score,
                    "confidence": round(cat_conf, 2),
                    "matched_terms": category_matches[:10]
                })

        # Sort by score descending
        scored_candidates.sort(key=lambda x: (x["score"], x["confidence"]), reverse=True)

        if not scored_candidates:
            return ClassificationResult(
                document_category=DocumentCategory.UNKNOWN,
                confidence=0.20,
                method="HYBRID_KEYWORD_REGEX_HEURISTIC",
                model_version=cls.MODEL_VERSION,
                matched_signals={"matched_terms": [], "match_count": 0},
                alternative_classifications=[],
                review_required=True,
                processing_status="REVIEW_REQUIRED"
            )

        top_candidate = scored_candidates[0]
        best_category = top_candidate["category"]
        confidence = top_candidate["confidence"]
        matched_terms = top_candidate["matched_terms"]
        best_score = top_candidate["score"]

        # Filter low confidence or ambiguities
        review_required = False
        if confidence < minimum_confidence:
            best_category = DocumentCategory.UNKNOWN
            review_required = True

        # Check if multiple categories tied or very close
        alternatives = []
        if len(scored_candidates) > 1:
            for alt in scored_candidates[1:4]:
                alternatives.append({
                    "category": alt["category"],
                    "confidence": alt["confidence"],
                    "score": alt["score"]
                })
            # If top two candidates have very close score, mark review required
            if scored_candidates[1]["score"] == top_candidate["score"]:
                review_required = True

        processing_status = "REVIEW_REQUIRED" if (review_required or best_category == DocumentCategory.UNKNOWN) else "CLASSIFIED"

        return ClassificationResult(
            document_category=best_category,
            confidence=confidence,
            method="HYBRID_KEYWORD_REGEX_HEURISTIC",
            model_version=cls.MODEL_VERSION,
            matched_signals={"matched_terms": matched_terms[:10], "match_count": best_score},
            alternative_classifications=alternatives,
            review_required=review_required,
            processing_status=processing_status
        )
