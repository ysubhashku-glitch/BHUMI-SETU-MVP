import uuid
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.services.ocr_engine import OCRResult, OCRSpanResult

class ParsedField:
    def __init__(
        self,
        field_name: str,
        raw_value: Optional[str],
        normalized_value: Optional[Any],
        unit: Optional[str] = None,
        data_type: str = "STRING",
        confidence: float = 1.0,
        span: Optional[OCRSpanResult] = None,
        page_number: int = 1
    ):
        self.field_name = field_name
        self.raw_value = raw_value
        self.normalized_value = normalized_value
        self.unit = unit
        self.data_type = data_type
        self.confidence = round(confidence, 2)
        self.span = span
        self.page_number = page_number

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "unit": self.unit,
            "data_type": self.data_type,
            "confidence": self.confidence,
            "page_number": self.page_number,
            "span": self.span.to_dict() if self.span else None
        }

class DocumentParseResult:
    def __init__(
        self,
        document_category: str,
        parser_name: str,
        parser_version: str,
        fields: List[ParsedField],
        unparsed_spans: List[OCRSpanResult],
        metadata: Dict[str, Any]
    ):
        self.document_category = document_category
        self.parser_name = parser_name
        self.parser_version = parser_version
        self.fields = fields
        self.unparsed_spans = unparsed_spans
        self.metadata = metadata

    def get_field(self, field_name: str) -> Optional[ParsedField]:
        for f in self.fields:
            if f.field_name == field_name:
                return f
        return None

class DocumentParser(ABC):
    """
    Abstract base class for specialized revenue document parsers.
    Parsers extract typed entities, preserve span coordinates, and handle missing values as UNKNOWN.
    """
    @abstractmethod
    def parse(self, ocr_result: OCRResult) -> DocumentParseResult:
        pass
