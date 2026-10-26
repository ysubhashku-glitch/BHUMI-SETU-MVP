import re
from typing import List
from app.models.evidence import DocumentCategory
from app.services.ocr_engine import OCRResult
from app.services.normalization_service import NormalizationService
from app.services.parsers.base_parser import DocumentParser, ParsedField, DocumentParseResult

class MutationParser(DocumentParser):
    PARSER_NAME = "MutationParser"
    PARSER_VERSION = "1.0.0"

    def parse(self, ocr_result: OCRResult) -> DocumentParseResult:
        fields: List[ParsedField] = []
        combined_text = ocr_result.combined_text

        # Case Number
        m_case = re.search(r"case\s*(?:no\.?|number)?\s*:\s*([0-9\/\-]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="mutation_case_number",
            raw_value=m_case.group(1).strip() if m_case else None,
            normalized_value=m_case.group(1).strip() if m_case else "UNKNOWN",
            confidence=0.96 if m_case else 0.0
        ))

        # Order Date
        m_date = re.search(r"order\s*date\s*:\s*([0-9\-\/]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="order_date",
            raw_value=m_date.group(1).strip() if m_date else None,
            normalized_value=m_date.group(1).strip() if m_date else None,
            data_type="DATE",
            confidence=0.95 if m_date else 0.0
        ))

        # Transferor (Seller) & Transferee (Buyer)
        m_tr = re.search(r"transferor\s*(?:\([^)]*\))?\s*:\s*([^\n,]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="transferor_name",
            raw_value=m_tr.group(1).strip() if m_tr else None,
            normalized_value=m_tr.group(1).strip() if m_tr else "UNKNOWN",
            data_type="ENTITY",
            confidence=0.92 if m_tr else 0.0
        ))

        m_te = re.search(r"transferee\s*(?:\([^)]*\))?\s*:\s*([^\n,]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="transferee_name",
            raw_value=m_te.group(1).strip() if m_te else None,
            normalized_value=m_te.group(1).strip() if m_te else "UNKNOWN",
            data_type="ENTITY",
            confidence=0.92 if m_te else 0.0
        ))

        # Deed Reference
        m_deed_ref = re.search(r"deed\s*(?:reference|no\.?)?\s*([0-9\/]+)", combined_text, re.IGNORECASE)
        fields.append(ParsedField(
            field_name="deed_reference",
            raw_value=m_deed_ref.group(1).strip() if m_deed_ref else None,
            normalized_value=m_deed_ref.group(1).strip() if m_deed_ref else None,
            confidence=0.90 if m_deed_ref else 0.0
        ))

        # Mutated Area
        m_area = re.search(r"mutated\s*area\s*:\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_area = m_area.group(1).strip() if m_area else None
        norm_area = NormalizationService.normalize_area(raw_area) if raw_area else None
        fields.append(ParsedField(
            field_name="mutated_area",
            raw_value=raw_area,
            normalized_value=norm_area.to_dict() if norm_area else None,
            unit=norm_area.raw_unit if norm_area else None,
            data_type="DECIMAL",
            confidence=0.94 if norm_area else 0.0
        ))

        # Mutation Status
        m_status = re.search(r"status\s*:\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_status = m_status.group(1).strip() if m_status else "PENDING"
        norm_status = "APPROVED" if "approved" in raw_status.lower() or "sanctioned" in raw_status.lower() else "PENDING"
        fields.append(ParsedField(
            field_name="mutation_status",
            raw_value=raw_status,
            normalized_value=norm_status,
            confidence=0.95
        ))

        return DocumentParseResult(
            document_category=DocumentCategory.MUTATION_RECORD,
            parser_name=self.PARSER_NAME,
            parser_version=self.PARSER_VERSION,
            fields=fields,
            unparsed_spans=[],
            metadata={"extracted_field_count": len(fields)}
        )
