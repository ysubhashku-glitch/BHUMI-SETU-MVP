import re
from typing import List
from app.models.evidence import DocumentCategory
from app.services.ocr_engine import OCRResult
from app.services.parsers.base_parser import DocumentParser, ParsedField, DocumentParseResult

class EncumbranceParser(DocumentParser):
    PARSER_NAME = "EncumbranceParser"
    PARSER_VERSION = "1.0.0"

    def parse(self, ocr_result: OCRResult) -> DocumentParseResult:
        fields: List[ParsedField] = []
        combined_text = ocr_result.combined_text

        # Search Period
        m_period = re.search(r"search\s*period\s*:\s*([^\n]+)", combined_text, re.IGNORECASE)
        raw_period = m_period.group(1).strip() if m_period else None
        fields.append(ParsedField(
            field_name="search_period",
            raw_value=raw_period,
            normalized_value=raw_period if raw_period else "UNKNOWN",
            confidence=0.92 if raw_period else 0.0
        ))

        # Encumbrance Status
        is_nil = bool(re.search(r"nil\s*encumbrance", combined_text, re.IGNORECASE))
        has_mortgage = bool(re.search(r"mortgage|hypothecation|bank\s*charge", combined_text, re.IGNORECASE))

        status_norm = "NIL_ENCUMBRANCE" if is_nil and not has_mortgage else ("ENCUMBERED" if has_mortgage else "REQUIRES_REVIEW")
        fields.append(ParsedField(
            field_name="encumbrance_status",
            raw_value="NIL" if is_nil else "RECORDED_ENTRIES",
            normalized_value=status_norm,
            confidence=0.95
        ))

        return DocumentParseResult(
            document_category=DocumentCategory.ENCUMBRANCE_CERTIFICATE,
            parser_name=self.PARSER_NAME,
            parser_version=self.PARSER_VERSION,
            fields=fields,
            unparsed_spans=[],
            metadata={"extracted_field_count": len(fields)}
        )
