import re
from typing import List, Dict, Any, Optional
from app.models.evidence import DocumentCategory
from app.services.ocr_engine import OCRResult, OCRSpanResult
from app.services.normalization_service import NormalizationService
from app.services.parsers.base_parser import DocumentParser, ParsedField, DocumentParseResult
from app.services.parsers.chauhaddi_extractor import ChauhaddiExtractor

class KhatiyanParser(DocumentParser):
    PARSER_NAME = "KhatiyanParser"
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
        combined_text = ocr_result.combined_text

        # 1. District, Circle, Mauza / Thana No (Bilingual)
        m_dist = re.search(r"(?:district|जिला)\s*[:\-]?\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_dist = m_dist.group(1).strip() if m_dist else None
        fields.append(ParsedField(
            field_name="district",
            raw_value=raw_dist,
            normalized_value=raw_dist.title() if raw_dist else "UNKNOWN",
            confidence=0.95 if m_dist else 0.0,
            page_number=self._find_page_number_for_text(raw_dist, ocr_result)
        ))

        m_circle = re.search(r"(?:anchal|circle|अंचल|प्रखंड)\s*[:\-]?\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_circle = m_circle.group(1).strip() if m_circle else None
        fields.append(ParsedField(
            field_name="circle",
            raw_value=raw_circle,
            normalized_value=raw_circle.title() if raw_circle else "UNKNOWN",
            confidence=0.95 if m_circle else 0.0,
            page_number=self._find_page_number_for_text(raw_circle, ocr_result)
        ))

        m_mauza = re.search(r"(?:mauza|village|मौजा|ग्राम)\s*[:\-]?\s*([^\n,(]+)", combined_text, re.IGNORECASE)
        raw_mauza = m_mauza.group(1).strip() if m_mauza else None
        fields.append(ParsedField(
            field_name="village",
            raw_value=raw_mauza,
            normalized_value=raw_mauza.title() if raw_mauza else "UNKNOWN",
            confidence=0.95 if m_mauza else 0.0,
            page_number=self._find_page_number_for_text(raw_mauza, ocr_result)
        ))

        m_thana = re.search(r"(?:thana\s*(?:no\.?|number)?|थाना\s*(?:नं\.?|संख्या)?)\s*[:\-]?\s*([0-9]+)", combined_text, re.IGNORECASE)
        raw_thana = m_thana.group(1).strip() if m_thana else None
        fields.append(ParsedField(
            field_name="thana_number",
            raw_value=raw_thana,
            normalized_value=raw_thana if raw_thana else "UNKNOWN",
            confidence=0.95 if m_thana else 0.0,
            page_number=self._find_page_number_for_text(raw_thana, ocr_result)
        ))

        # 2. Raiyat Name & Father/Husband (Bilingual)
        m_raiyat = re.search(r"(?:raiyat|रैयत(?:दार)?(?:\s*का\s*नाम)?)\s*(?:\([^)]*\))?\s*[:\-]?\s*([^\n,]+(?:,\s*(?:s/o|w/o|d/o|आत्मज|पिता)[^\n,]+)?)", combined_text, re.IGNORECASE)
        raw_raiyat = m_raiyat.group(1).strip() if m_raiyat else None
        norm_raiyat = NormalizationService.normalize_person_name(raw_raiyat) if raw_raiyat else None
        fields.append(ParsedField(
            field_name="recorded_raiyat",
            raw_value=raw_raiyat,
            normalized_value=norm_raiyat.to_dict() if norm_raiyat else "UNKNOWN",
            data_type="ENTITY",
            confidence=0.95 if norm_raiyat else 0.0,
            page_number=self._find_page_number_for_text(raw_raiyat, ocr_result)
        ))

        # 3. Caste / Tribal Status
        m_caste = re.search(r"(?:caste|community|जाति)\s*[:\-]?\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_caste = m_caste.group(1).strip() if m_caste else None
        is_tribal = False
        if raw_caste and any(w in raw_caste.lower() for w in ["santhal", "tribal", "st", "munda", "oraon", "अनुसूचित जनजाति"]):
            is_tribal = True
        fields.append(ParsedField(
            field_name="caste_community",
            raw_value=raw_caste,
            normalized_value={"raw_caste": raw_caste, "is_tribal": is_tribal},
            confidence=0.92 if raw_caste else 0.0,
            page_number=self._find_page_number_for_text(raw_caste, ocr_result)
        ))

        # 4. Khata Number
        m_khata = re.search(r"(?:khata|खाता)\s*(?:number|no\.?|संख्या)?\s*[:\-]?\s*([a-zA-Z0-9\/\-]+)", combined_text, re.IGNORECASE)
        raw_khata = m_khata.group(1).strip() if m_khata else None
        fields.append(ParsedField(
            field_name="khata_number",
            raw_value=raw_khata,
            normalized_value=raw_khata if raw_khata else "UNKNOWN",
            confidence=0.98 if m_khata else 0.0,
            page_number=self._find_page_number_for_text(raw_khata, ocr_result)
        ))

        # 5. Plot / Khesra & Land Nature
        m_plot = re.search(r"(?:plot|khesra|खेसरा|प्लाट)\s*(?:no\.?|number|संख्या)?\s*[:\-]?\s*([0-9]+[0-9\/a-zA-Z\-]*)", combined_text, re.IGNORECASE)
        raw_plot = m_plot.group(1).strip() if m_plot else None
        fields.append(ParsedField(
            field_name="plot_number",
            raw_value=raw_plot,
            normalized_value=raw_plot if raw_plot else "UNKNOWN",
            confidence=0.96 if m_plot else 0.0,
            page_number=self._find_page_number_for_text(raw_plot, ocr_result)
        ))

        m_nature = re.search(r"(?:nature|किस्म\s*जमीन|land\s*classification)\s*[:\-]?\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_nature = m_nature.group(1).strip() if m_nature else None
        fields.append(ParsedField(
            field_name="land_classification",
            raw_value=raw_nature,
            normalized_value=raw_nature.title() if raw_nature else "UNKNOWN",
            confidence=0.90 if raw_nature else 0.0,
            page_number=self._find_page_number_for_text(raw_nature, ocr_result)
        ))

        # 6. Recorded Area
        m_area = re.search(r"(?:recorded\s*area|area|रकबा|क्षेत्रफल)\s*[:\-]?\s*([^\n,]+)", combined_text, re.IGNORECASE)
        raw_area = m_area.group(1).strip() if m_area else None
        norm_area = NormalizationService.normalize_area(raw_area) if raw_area else None
        fields.append(ParsedField(
            field_name="recorded_area",
            raw_value=raw_area,
            normalized_value=norm_area.to_dict() if norm_area else None,
            unit=norm_area.raw_unit if norm_area else None,
            data_type="DECIMAL",
            confidence=0.94 if norm_area else 0.0,
            page_number=self._find_page_number_for_text(raw_area, ocr_result)
        ))

        # 7. Annual Rent (Lagan)
        m_rent = re.search(r"(?:annual\s*rent|lagan|लगान|मालगुजारी)\s*[:\-]?\s*(?:rs\.?|inr|रु)?\s*([0-9\.]+)", combined_text, re.IGNORECASE)
        raw_rent = m_rent.group(1).strip() if m_rent else None
        fields.append(ParsedField(
            field_name="annual_rent",
            raw_value=raw_rent,
            normalized_value=float(m_rent.group(1)) if m_rent else None,
            unit="INR",
            data_type="DECIMAL",
            confidence=0.90 if m_rent else 0.0,
            page_number=self._find_page_number_for_text(raw_rent, ocr_result)
        ))

        # 8. Boundary Descriptions (if present in Khatiyan)
        chauhaddi_res = ChauhaddiExtractor.extract_boundaries(combined_text)
        if any([chauhaddi_res.north, chauhaddi_res.south, chauhaddi_res.east, chauhaddi_res.west]):
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
            document_category=DocumentCategory.KHATIYAN,
            parser_name=self.PARSER_NAME,
            parser_version=self.PARSER_VERSION,
            fields=fields,
            unparsed_spans=[],
            metadata={"extracted_field_count": len(fields)}
        )
