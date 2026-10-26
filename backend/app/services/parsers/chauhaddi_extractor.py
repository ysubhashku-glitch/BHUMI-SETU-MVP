"""
Bhumi Setu - Chauhaddi / Boundary Extraction Service.

Extracts four-sided directional boundary descriptions (North, South, East, West /
उत्तर, दक्षिण, पूरब, पश्चिम) from Hindi, English, and mixed Indic land documents.
Preserves verbatim raw text, extracts adjacent plot references, road frontage,
and adjoining neighbor names while maintaining strict epistemic boundaries.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class DirectionalBoundary(BaseModel):
    direction: str  # 'north', 'south', 'east', 'west'
    direction_label_raw: str  # e.g., 'North', 'उत्तर', 'N'
    raw_text: str  # Verbatim extracted boundary description
    normalized_description: str  # Cleaned, standardized text
    adjoining_plot_number: Optional[str] = None  # e.g., '113', '112/B'
    adjoining_neighbor_name: Optional[str] = None  # e.g., 'Binod Roy', 'Nij plot of seller'
    is_road_or_path: bool = False  # e.g., 'PWD Road', 'Common Rasta'
    road_width_feet: Optional[float] = None  # e.g., 20.0
    confidence: float = 0.90
    ambiguous: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ChauhaddiExtractionResult(BaseModel):
    boundaries: Dict[str, DirectionalBoundary] = Field(default_factory=dict)
    raw_block: Optional[str] = None
    directions_found_count: int = 0
    has_all_four_directions: bool = False
    disclaimer: str = (
        "Textual boundary descriptions reflect historical recitals in the source document. "
        "They do not certify current ground possession or replace physical field Amin survey."
    )

    @property
    def raw_text(self) -> Optional[str]:
        return self.raw_block

    @property
    def confidence(self) -> float:
        if not self.boundaries:
            return 0.0
        return round(sum(b.confidence for b in self.boundaries.values()) / len(self.boundaries), 2)

    @property
    def north(self) -> Optional[DirectionalBoundary]:
        return self.boundaries.get("north")

    @property
    def south(self) -> Optional[DirectionalBoundary]:
        return self.boundaries.get("south")

    @property
    def east(self) -> Optional[DirectionalBoundary]:
        return self.boundaries.get("east")

    @property
    def west(self) -> Optional[DirectionalBoundary]:
        return self.boundaries.get("west")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ChauhaddiExtractor:
    """
    Dedicated extractor for Chauhaddi / Boundary recitals in Indian property deeds and survey khatiyans.
    Supports English ('North', 'N', 'South', 'S', etc.) and Hindi Devanagari ('उत्तर', 'दक्षिण', 'पूरब', 'पश्चिम').
    """

    # Direction matching patterns
    DIRECTION_PATTERNS = {
        "north": [
            r"(?:north|उत्तर|उ०)\s*[:=\-–]\s*([^\n;,\.\|]+)",
            r"(?:north|उत्तर)\s+by\s+([^\n;,\.\|]+)",
            r"चौहद्दी\s*उत्तर\s*[:=\-–]?\s*([^\n;,\.\|]+)",
            r"(?:^|\n|\s)N\s*[:=\-–]\s*([^\n;,\.\|]+)",
        ],
        "south": [
            r"(?:south|दक्षिण|द०)\s*[:=\-–]\s*([^\n;,\.\|]+)",
            r"(?:south|दक्षिण)\s+by\s+([^\n;,\.\|]+)",
            r"चौहद्दी\s*दक्षिण\s*[:=\-–]?\s*([^\n;,\.\|]+)",
            r"(?:^|\n|\s)S\s*[:=\-–]\s*([^\n;,\.\|]+)",
        ],
        "east": [
            r"(?:east|पूरब|पूर्व|पू०)\s*[:=\-–]\s*([^\n;,\.\|]+)",
            r"(?:east|पूरब|पूर्व)\s+by\s+([^\n;,\.\|]+)",
            r"चौहद्दी\s*पूरब\s*[:=\-–]?\s*([^\n;,\.\|]+)",
            r"(?:^|\n|\s)E\s*[:=\-–]\s*([^\n;,\.\|]+)",
        ],
        "west": [
            r"(?:west|पश्चिम|प०)\s*[:=\-–]\s*([^\n;,\.\|]+)",
            r"(?:west|पश्चिम)\s+by\s+([^\n;,\.\|]+)",
            r"चौहद्दी\s*पश्चिम\s*[:=\-–]?\s*([^\n;,\.\|]+)",
            r"(?:^|\n|\s)W\s*[:=\-–]\s*([^\n;,\.\|]+)",
        ],
    }

    @classmethod
    def extract_boundaries(cls, text: str) -> ChauhaddiExtractionResult:
        """
        Parses text for Chauhaddi descriptions, analyzing road widths,
        adjoining plot numbers, and neighbor identities.
        """
        if not text:
            return ChauhaddiExtractionResult()

        boundaries: Dict[str, DirectionalBoundary] = {}
        
        # Locate Chauhaddi block if present for context
        m_block = re.search(
            r"(?:chauhaddi|chauhadri|boundaries|चौहद्दी|सीमाएं)[\s\:\-–]+(.*?)(?=\n\n|[A-Z][a-z]+:|$)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        raw_block = m_block.group(0).strip() if m_block else None
        target_text = raw_block if raw_block else text

        for direction, patterns in cls.DIRECTION_PATTERNS.items():
            for pat in patterns:
                m = re.search(pat, target_text, re.IGNORECASE)
                if m:
                    raw_val = m.group(1).strip()
                    # Clean trailing commas or dashes
                    clean_val = re.sub(r"^[–\-:\s]+|[–\-:\s;,]+$", "", raw_val).strip()
                    if clean_val and direction not in boundaries:
                        dir_boundary = cls._analyze_boundary_detail(direction, clean_val)
                        boundaries[direction] = dir_boundary
                        break

        return ChauhaddiExtractionResult(
            boundaries=boundaries,
            raw_block=raw_block,
            directions_found_count=len(boundaries),
            has_all_four_directions=len(boundaries) == 4
        )

    @classmethod
    def _analyze_boundary_detail(cls, direction: str, raw_text: str) -> DirectionalBoundary:
        """
        Inspects boundary text to extract road features, plot numbers, and neighbor references.
        """
        lower = raw_text.lower()
        is_road = any(w in lower for w in [
            "road", "rasta", "रास्ता", "सड़क", "मार्ग", "गली", "pwd", "lane", "path", "नाला", "पगडंडी", "डहर", "canal"
        ])

        # Road width in feet
        road_width = None
        if is_road:
            m_width = re.search(r"(\d+(?:\.\d+)?)\s*(?:ft|feet|फीट|फिट|फुट)", lower)
            if m_width:
                try:
                    road_width = float(m_width.group(1))
                except ValueError:
                    road_width = None

        # Adjoining plot number (e.g., 'Plot No 113', 'खेसरा 114')
        adjoining_plot = None
        m_plot = re.search(r"(?:plot|khesra|खेसरा|प्लॉट)\s*(?:no\.?|संख्या)?\s*([0-9]+[a-zA-Z\/\d]*)", raw_text, re.IGNORECASE)
        if m_plot:
            adjoining_plot = m_plot.group(1).strip()

        # Adjoining neighbor name (e.g. 'of Binod Roy', 'Nij plot of seller', 'राम कुमार')
        neighbor_name = None
        if "of " in lower:
            parts = re.split(r"of\s+", raw_text, flags=re.IGNORECASE)
            if len(parts) > 1:
                neighbor_name = parts[1].strip()
        elif "का" in raw_text or "की" in raw_text:
            m_hi = re.search(r"([^\n,]+)\s*(?:का|की)\s*(?:जमीन|प्लॉट|मकान|खेत)", raw_text)
            if m_hi:
                neighbor_name = m_hi.group(1).strip()

        confidence = 0.95 if (is_road or adjoining_plot or neighbor_name) else 0.85

        return DirectionalBoundary(
            direction=direction,
            direction_label_raw=direction.capitalize(),
            raw_text=raw_text,
            normalized_description=raw_text.strip(),
            adjoining_plot_number=adjoining_plot,
            adjoining_neighbor_name=neighbor_name,
            is_road_or_path=is_road,
            road_width_feet=road_width,
            confidence=confidence,
            ambiguous=False
        )
