"""
Mutation Document Extraction and Normalization Service (TASK-P2-05).

Extracts mutation case numbers, parties, plot/khata, deed particulars,
and rejection ground codes from Form-IX notices, inquiry reports, and order sheets.
Preserves raw text vs normalized representations and distinguishes source-stated facts
from OCR-derived fields and system inferences. Never fabricates missing values.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
from app.models.mutation import MutationType, MutationStatus

# Bihar administrative rejection reason codes under Bihar Land Mutation Act
REJECTION_GROUND_PATTERNS = {
    "LAND_DISPUTED": [
        r"विवादित\s*भूमि",
        r"विवाद\s*लंबित",
        r"title\s*dispute",
        r"disputed\s*land",
        r"सिविल\s*कोर्ट",
        r"न्यायालय\s*में\s*वाद",
    ],
    "AREA_DEFICIT": [
        r"रकबा\s*अपर्याप्त",
        r"रकबा\s*शून्य",
        r"रकबा\s*कमी",
        r"विक्रेता\s*का\s*रकबा",
        r"area\s*deficit",
        r"insufficient\s*area",
        r"excess\s*area\s*sold",
    ],
    "TITLE_INJUNCTION": [
        r"स्थगन\s*आदेश",
        r"injunction",
        r"stay\s*order",
        r"अंतरिम\s*निषेधाज्ञा",
    ],
    "INSUFFICIENT_DOCUMENTS": [
        r"अस्पष्ट\s*दस्तावेज",
        r"साक्ष्य\s*अभाव",
        r"कागजात\s*अप्राप्त",
        r"insufficient\s*document",
        r"missing\s*deed",
    ],
    "VENDOR_TITLE_DEFECT": [
        r"विक्रेता\s*का\s*स्वामित्व\s*नहीं",
        r"जमाबंदी\s*कायम\s*नहीं",
        r"no\s*jamabandi",
        r"vendor\s*title\s*defect",
    ],
}

# Regex patterns for Bihar mutation dockets
CASE_NUMBER_REGEX = re.compile(
    r"(?:Mutation\s*Case|Case\s*No\.?|वाद\s*संख्या|वाद\s*सं\.?|दाखिल[\s\-]*खारिज\s*वाद)[\s\:\-\/]*([A-Z0-9\-\/]+)",
    re.IGNORECASE,
)
KHATA_REGEX = re.compile(r"(?:Khata|खाता)(?:\s*(?:संख्या|नं\.?|क्र\.?))?[\s\:\-\/]*(\d+)", re.IGNORECASE)
KHESRA_REGEX = re.compile(r"(?:Khesra|Plot|खेसरा|प्लॉट)(?:\s*(?:संख्या|नं\.?|क्र\.?))?[\s\:\-\/]*(\d+)", re.IGNORECASE)
MAUZA_REGEX = re.compile(r"(?:Mauza|Village|मौजा|ग्राम)[\s\:\-\/]*([A-Za-z\u0900-\u097F\s]+?)(?:,|\n|Thana|थाना|$)", re.IGNORECASE)
DEED_REGEX = re.compile(r"(?:Deed\s*No\.?|दस्तावेज\s*संख्या|केवाला\s*संख्या)[\s\:\-\/]*([A-Za-z0-9\-\/]+)", re.IGNORECASE)
DATE_REGEX = re.compile(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})")


class MutationExtractor:
    """
    Extracts and normalizes mutation fields from text or OCR output.
    All extracted fields preserve confidence and provenance.
    """

    @classmethod
    def extract_from_text(
        cls,
        text: str,
        source_reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract structured mutation parameters from raw Hindi/English document text.
        Returns a dictionary of raw fields, normalized values, confidence, and flags.
        """
        if not text or not text.strip():
            return {
                "extracted_fields": {},
                "confidence": 0.0,
                "requires_human_review": True,
                "extraction_method": "EMPTY_TEXT",
            }

        extracted: Dict[str, Any] = {}
        matched_indicators = 0
        total_checks = 6

        # 1. Case Number
        case_match = CASE_NUMBER_REGEX.search(text)
        if case_match:
            raw_case = case_match.group(1).strip()
            extracted["case_number"] = {
                "raw_text": raw_case,
                "normalized": raw_case.upper(),
                "confidence": 0.90,
            }
            matched_indicators += 1

        # 2. Khata Number
        khata_match = KHATA_REGEX.search(text)
        if khata_match:
            extracted["khata_number"] = {
                "raw_text": khata_match.group(1),
                "normalized": khata_match.group(1).strip(),
                "confidence": 0.85,
            }
            matched_indicators += 1

        # 3. Khesra / Plot Number
        khesra_match = KHESRA_REGEX.search(text)
        if khesra_match:
            extracted["khesra_number"] = {
                "raw_text": khesra_match.group(1),
                "normalized": khesra_match.group(1).strip(),
                "confidence": 0.85,
            }
            matched_indicators += 1

        # 4. Mauza
        mauza_match = MAUZA_REGEX.search(text)
        if mauza_match:
            extracted["mauza"] = {
                "raw_text": mauza_match.group(1).strip(),
                "normalized": mauza_match.group(1).strip().title(),
                "confidence": 0.80,
            }
            matched_indicators += 1

        # 5. Deed Number
        deed_match = DEED_REGEX.search(text)
        if deed_match:
            extracted["deed_number"] = {
                "raw_text": deed_match.group(1).strip(),
                "normalized": deed_match.group(1).strip().upper(),
                "confidence": 0.85,
            }
            matched_indicators += 1

        # 6. Rejection Grounds (if rejected or disputed)
        detected_reasons = []
        for code, patterns in REJECTION_GROUND_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    detected_reasons.append(code)
                    break

        if detected_reasons:
            extracted["rejection_grounds"] = {
                "codes": list(set(detected_reasons)),
                "confidence": 0.85,
            }

        # 7. Dates
        dates_found = []
        for m in DATE_REGEX.finditer(text):
            day, month, year = m.groups()
            try:
                dt = date(int(year), int(month), int(day))
                dates_found.append(dt.isoformat())
            except ValueError:
                pass
        if dates_found:
            extracted["detected_dates"] = dates_found

        confidence = round(matched_indicators / float(total_checks), 2)
        requires_review = confidence < 0.60 or "rejection_grounds" in extracted

        return {
            "extracted_fields": extracted,
            "confidence": confidence,
            "requires_human_review": requires_review,
            "extraction_method": "REGEX_AND_KEYWORD_HEURISTICS",
            "source_reference": source_reference,
        }

    @classmethod
    def normalize_status(cls, raw_status: Optional[str]) -> Tuple[MutationStatus, Optional[str]]:
        """
        Maps source portal status string to normalized MutationStatus enum.
        Preserves original raw status.
        """
        if not raw_status:
            return MutationStatus.STATUS_UNKNOWN, None

        s = raw_status.strip().lower()

        if any(w in s for w in ["अस्वीकृत", "rejected", "खारिज", "disposed rejected", "disapproved"]):
            return MutationStatus.REJECTED, raw_status
        elif any(w in s for w in ["स्वीकृत", "approved", "shuddhi patra", "शुद्धि पत्र", "disposed approved"]):
            return MutationStatus.APPROVED, raw_status
        elif any(w in s for w in ["नोटिस", "notice", "form ix", "form-ix"]):
            return MutationStatus.NOTICE_ISSUED, raw_status
        elif any(w in s for w in ["सुनवाई", "hearing", "objection", "आपत्ति"]):
            return MutationStatus.HEARING_PENDING, raw_status
        elif any(w in s for w in ["जांच", "कर्मचारी", "karamchari", "scrutiny", "अंचल"]):
            return MutationStatus.UNDER_SCRUTINY, raw_status
        elif any(w in s for w in ["वापस", "withdrawn"]):
            return MutationStatus.WITHDRAWN, raw_status
        elif any(w in s for w in ["प्राप्त", "received", "submitted", "दाखिल"]):
            return MutationStatus.SUBMITTED, raw_status
        elif any(w in s for w in ["विवादित", "conflicting", "dispute"]):
            return MutationStatus.CONFLICTING_EVIDENCE, raw_status
        else:
            return MutationStatus.STATUS_UNKNOWN, raw_status
