import re
from typing import List, Dict, Any, Optional
from app.models.evidence import DocumentCategory
from app.services.ocr_engine import OCRResult, OCRSpanResult
from app.services.normalization_service import NormalizationService
from app.services.parsers.base_parser import DocumentParser, ParsedField, DocumentParseResult
from app.services.parsers.chauhaddi_extractor import ChauhaddiExtractor

class SaleDeedParser(DocumentParser):
    PARSER_NAME = "SaleDeedParser"
    PARSER_VERSION = "1.1.0"

    def _find_page_number_for_text(self, text_snippet: Optional[str], ocr_result: OCRResult) -> int:
        """Traces the field value back to its source page in a multi-page document."""
        if not text_snippet or not ocr_result.pages:
            return 1
        clean_snippet = text_snippet.strip().lower()
        if not clean_snippet:
            return 1
        for p in ocr_result.pages:
            if clean_snippet in p.full_text.lower():
                return p.page_number
        return 1

    def parse(self, ocr_result: OCRResult) -> DocumentParseResult:
        fields: List[ParsedField] = []
        unparsed_spans: List[OCRSpanResult] = []
        combined_text = ocr_result.combined_text

        # 1. District, Circle, Village / Mauza (Bilingual)
        m_dist = re.search(r"(?:district|जिला)\s*[:\-]?\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_dist = m_dist.group(1).strip() if m_dist else None
        fields.append(ParsedField(
            field_name="district",
            raw_value=raw_dist,
            normalized_value=raw_dist.title() if raw_dist else "UNKNOWN",
            confidence=0.95 if m_dist else 0.0,
            page_number=self._find_page_number_for_text(raw_dist, ocr_result)
        ))

        m_circle = re.search(r"(?:circle|anchal|अंचल|प्रखंड)\s*[:\-]?\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_circle = m_circle.group(1).strip() if m_circle else None
        fields.append(ParsedField(
            field_name="circle",
            raw_value=raw_circle,
            normalized_value=raw_circle.title() if raw_circle else "UNKNOWN",
            confidence=0.95 if m_circle else 0.0,
            page_number=self._find_page_number_for_text(raw_circle, ocr_result)
        ))

        m_mauza = re.search(r"(?:mauza|village|gram|मौजा|ग्राम)\s*[:\-]?\s*([^\n,(]+)", combined_text, re.IGNORECASE)
        raw_mauza = m_mauza.group(1).strip() if m_mauza else None
        fields.append(ParsedField(
            field_name="village",
            raw_value=raw_mauza,
            normalized_value=raw_mauza.title() if raw_mauza else "UNKNOWN",
            confidence=0.95 if m_mauza else 0.0,
            page_number=self._find_page_number_for_text(raw_mauza, ocr_result)
        ))

        # 2. Khata and Plot / Khesra (Bilingual)
        m_khata = re.search(r"(?:khata|खाता)\s*(?:no\.?|number|संख्या)?\s*[:\-]?\s*([a-zA-Z0-9\/\-]+)", combined_text, re.IGNORECASE)
        raw_khata = m_khata.group(1).strip() if m_khata else None
        fields.append(ParsedField(
            field_name="khata_number",
            raw_value=raw_khata,
            normalized_value=raw_khata if raw_khata else "UNKNOWN",
            confidence=0.98 if m_khata else 0.0,
            page_number=self._find_page_number_for_text(raw_khata, ocr_result)
        ))

        m_plot = re.search(r"(?:plot|khesra|खेसरा|प्लाट)\s*(?:no\.?|number|संख्या)?\s*[:\-]?\s*([0-9]+[0-9\/a-zA-Z\-]*)", combined_text, re.IGNORECASE)
        raw_plot = m_plot.group(1).strip() if m_plot else None
        fields.append(ParsedField(
            field_name="plot_number",
            raw_value=raw_plot,
            normalized_value=raw_plot if raw_plot else "UNKNOWN",
            confidence=0.98 if m_plot else 0.0,
            page_number=self._find_page_number_for_text(raw_plot, ocr_result)
        ))

        # 3. Area with Normalization (Bilingual)
        m_area = re.search(r"(?:area|रकबा|क्षेत्रफल)\s*[:\-]?\s*([^\n,(]+(?:\(.*?\))?)", combined_text, re.IGNORECASE)
        raw_area = m_area.group(1).strip() if m_area else None
        norm_area = NormalizationService.normalize_area(raw_area) if raw_area else None
        fields.append(ParsedField(
            field_name="recorded_area",
            raw_value=raw_area,
            normalized_value=norm_area.to_dict() if norm_area else None,
            unit=norm_area.raw_unit if norm_area else None,
            data_type="DECIMAL",
            confidence=0.92 if norm_area else 0.0,
            page_number=self._find_page_number_for_text(raw_area, ocr_result)
        ))

        # 4. Seller and Buyer Parties (Bilingual)
        m_seller = re.search(r"(?:seller|विक्रेता)\s*(?:\([^)]*\))?\s*[:\-]?\s*([^\n,]+(?:,\s*(?:s/o|w/o|d/o|आत्मज|वल्द)[^\n,]+)?)", combined_text, re.IGNORECASE)
        raw_seller = m_seller.group(1).strip() if m_seller else None
        norm_seller = NormalizationService.normalize_person_name(raw_seller) if raw_seller else None
        fields.append(ParsedField(
            field_name="seller_name",
            raw_value=raw_seller,
            normalized_value=norm_seller.to_dict() if norm_seller else "UNKNOWN",
            data_type="ENTITY",
            confidence=0.94 if norm_seller else 0.0,
            page_number=self._find_page_number_for_text(raw_seller, ocr_result)
        ))

        m_buyer = re.search(r"(?:buyer|(?<!वि)क्रेता)\s*(?:\([^)]*\))?\s*[:\-]?\s*([^\n,]+(?:,\s*(?:s/o|w/o|d/o|आत्मज|वल्द|पति)[^\n,]+)?)", combined_text, re.IGNORECASE)
        raw_buyer = m_buyer.group(1).strip() if m_buyer else None
        norm_buyer = NormalizationService.normalize_person_name(raw_buyer) if raw_buyer else None
        fields.append(ParsedField(
            field_name="buyer_name",
            raw_value=raw_buyer,
            normalized_value=norm_buyer.to_dict() if norm_buyer else "UNKNOWN",
            data_type="ENTITY",
            confidence=0.94 if norm_buyer else 0.0,
            page_number=self._find_page_number_for_text(raw_buyer, ocr_result)
        ))

        # 5. Deed and Registration Metadata
        m_deed = re.search(r"(?:deed|दस्तावेज़|विलेख)\s*(?:no\.?|number|संख्या)?\s*[:\-]?\s*([0-9\/]+)", combined_text, re.IGNORECASE)
        raw_deed = m_deed.group(1).strip() if m_deed else None
        fields.append(ParsedField(
            field_name="deed_number",
            raw_value=raw_deed,
            normalized_value=raw_deed if raw_deed else "UNKNOWN",
            confidence=0.96 if m_deed else 0.0,
            page_number=self._find_page_number_for_text(raw_deed, ocr_result)
        ))

        m_reg_date = re.search(r"(?:registration\s*date|निबंधन\s*तिथि)\s*[:\-]?\s*([0-9\-\/]+)", combined_text, re.IGNORECASE)
        raw_reg_date = m_reg_date.group(1).strip() if m_reg_date else None
        fields.append(ParsedField(
            field_name="registration_date",
            raw_value=raw_reg_date,
            normalized_value=raw_reg_date if raw_reg_date else None,
            data_type="DATE",
            confidence=0.95 if m_reg_date else 0.0,
            page_number=self._find_page_number_for_text(raw_reg_date, ocr_result)
        ))

        m_consideration = re.search(r"(?:consideration|प्रतिफल\s*राशि|मालगुजारी)\s*[:\-]?\s*(?:rs\.?|inr|रु)?\s*([0-9,]+)", combined_text, re.IGNORECASE)
        raw_cons = m_consideration.group(1).strip() if m_consideration else None
        num_cons = float(raw_cons.replace(",", "")) if raw_cons else None
        fields.append(ParsedField(
            field_name="consideration_amount",
            raw_value=raw_cons,
            normalized_value=num_cons,
            unit="INR",
            data_type="DECIMAL",
            confidence=0.95 if num_cons else 0.0,
            page_number=self._find_page_number_for_text(raw_cons, ocr_result)
        ))

        # 6. Dedicated Chauhaddi and Boundary Extraction
        chauhaddi_res = ChauhaddiExtractor.extract_boundaries(combined_text)
        fields.append(ParsedField(
            field_name="chauhaddi_structured",
            raw_value=chauhaddi_res.raw_text,
            normalized_value=chauhaddi_res.to_dict(),
            confidence=chauhaddi_res.confidence,
            page_number=self._find_page_number_for_text(chauhaddi_res.raw_text, ocr_result)
        ))

        for direction in ["north", "south", "east", "west"]:
            dir_bound = getattr(chauhaddi_res, direction)
            raw_b = dir_bound.raw_text if dir_bound else None
            fields.append(ParsedField(
                field_name=f"boundary_{direction}",
                raw_value=raw_b,
                normalized_value=dir_bound.to_dict() if dir_bound else "UNKNOWN",
                confidence=dir_bound.confidence if dir_bound else 0.0,
                page_number=self._find_page_number_for_text(raw_b, ocr_result)
            ))

        return DocumentParseResult(
            document_category=DocumentCategory.SALE_DEED,
            parser_name=self.PARSER_NAME,
            parser_version=self.PARSER_VERSION,
            fields=fields,
            unparsed_spans=unparsed_spans,
            metadata={"extracted_field_count": len(fields)}
        )
