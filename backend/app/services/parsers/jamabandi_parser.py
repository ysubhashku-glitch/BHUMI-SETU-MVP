import re
from typing import List
from app.models.evidence import DocumentCategory
from app.services.ocr_engine import OCRResult
from app.services.parsers.base_parser import DocumentParser, ParsedField, DocumentParseResult

class JamabandiParser(DocumentParser):
    PARSER_NAME = "JamabandiParser"
    PARSER_VERSION = "1.0.0"

    def parse(self, ocr_result: OCRResult) -> DocumentParseResult:
        fields: List[ParsedField] = []
        combined_text = ocr_result.combined_text

        # Jamabandi Number
        m_jamabandi = re.search(r"jamabandi\s*(?:no\.?|number)?\s*:\s*([0-9a-zA-Z\/]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="jamabandi_number",
            raw_value=m_jamabandi.group(1).strip() if m_jamabandi else None,
            normalized_value=m_jamabandi.group(1).strip() if m_jamabandi else "UNKNOWN",
            confidence=0.95 if m_jamabandi else 0.0
        ))

        # Tenant Name
        m_tenant = re.search(r"tenant\s*name\s*(?:\([^)]*\))?\s*:\s*([^\n,]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="recorded_tenant",
            raw_value=m_tenant.group(1).strip() if m_tenant else None,
            normalized_value=m_tenant.group(1).strip() if m_tenant else "UNKNOWN",
            data_type="ENTITY",
            confidence=0.94 if m_tenant else 0.0
        ))

        # Khata and Plot
        m_khata = re.search(r"khata\s*(?:no\.?|number)?\s*:\s*([0-9a-zA-Z\/]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="khata_number",
            raw_value=m_khata.group(1).strip() if m_khata else None,
            normalized_value=m_khata.group(1).strip() if m_khata else "UNKNOWN",
            confidence=0.98 if m_khata else 0.0
        ))

        m_plot = re.search(r"plot\s*(?:no\.?|number)?\s*:\s*([0-9a-zA-Z\/]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="plot_number",
            raw_value=m_plot.group(1).strip() if m_plot else None,
            normalized_value=m_plot.group(1).strip() if m_plot else "UNKNOWN",
            confidence=0.98 if m_plot else 0.0
        ))

        # Mutation Reference
        m_mut = re.search(r"(?:dakhil\s*kharij|mutation)\s*(?:case\s*no\.?)?\s*([0-9\/\-]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="mutation_reference",
            raw_value=m_mut.group(1).strip() if m_mut else None,
            normalized_value=m_mut.group(1).strip() if m_mut else None,
            confidence=0.92 if m_mut else 0.0
        ))

        return DocumentParseResult(
            document_category=DocumentCategory.JAMABANDI,
            parser_name=self.PARSER_NAME,
            parser_version=self.PARSER_VERSION,
            fields=fields,
            unparsed_spans=[],
            metadata={"extracted_field_count": len(fields)}
        )
