import re
from typing import Dict, Any, Optional, Tuple

class NormalizedArea:
    def __init__(
        self,
        raw_string: str,
        raw_numeric: Optional[float],
        raw_unit: Optional[str],
        normalized_sqm: Optional[float],
        normalized_acres: Optional[float],
        normalized_decimals: Optional[float],
        conversion_rule: str,
        is_uncertain: bool = False
    ):
        self.raw_string = raw_string
        self.raw_numeric = raw_numeric
        self.raw_unit = raw_unit
        self.normalized_sqm = round(normalized_sqm, 2) if normalized_sqm is not None else None
        self.normalized_acres = round(normalized_acres, 4) if normalized_acres is not None else None
        self.normalized_decimals = round(normalized_decimals, 2) if normalized_decimals is not None else None
        self.conversion_rule = conversion_rule
        self.is_uncertain = is_uncertain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_string": self.raw_string,
            "raw_numeric": self.raw_numeric,
            "raw_unit": self.raw_unit,
            "normalized_sqm": self.normalized_sqm,
            "normalized_acres": self.normalized_acres,
            "normalized_decimals": self.normalized_decimals,
            "conversion_rule": self.conversion_rule,
            "is_uncertain": self.is_uncertain
        }

class NormalizedPersonName:
    def __init__(
        self,
        raw_string: str,
        clean_name: str,
        relationship_prefix: Optional[str] = None,
        relative_name: Optional[str] = None,
        honorific: Optional[str] = None
    ):
        self.raw_string = raw_string
        self.clean_name = clean_name
        self.relationship_prefix = relationship_prefix  # 'S/O', 'W/O', 'D/O'
        self.relative_name = relative_name
        self.honorific = honorific

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_string": self.raw_string,
            "clean_name": self.clean_name,
            "relationship_prefix": self.relationship_prefix,
            "relative_name": self.relative_name,
            "honorific": self.honorific
        }

class NormalizationService:
    """
    Controlled normalization layer.
    Preserves original spelling and units while calculating standard metric references.
    """
    # 1 Acre = 4046.8564 sqm = 100 Decimals = 32 Katha in standard Bihar
    # 1 Decimal = 40.468564 sqm
    # 1 Katha (standard Jharkhand/Bihar) = ~126.46 sqm
    # 1 Bigha = 20 Katha = ~2529.285 sqm
    # 1 Sq Ft = 0.092903 sqm
    # 1 Hectare = 10000.0 sqm = ~2.471 Acres
    SQM_PER_ACRE = 4046.8564
    SQM_PER_DECIMAL = 40.468564
    SQM_PER_KATHA = 126.46
    SQM_PER_BIGHA = 2529.285
    SQM_PER_SQFT = 0.092903
    SQM_PER_HECTARE = 10000.0

    @classmethod
    def normalize_area(cls, area_text: str) -> Optional[NormalizedArea]:
        if not area_text or not area_text.strip():
            return None

        clean_text = area_text.strip().lower()

        # Check for bare number without unit (e.g. "100" or "1.5")
        if re.match(r"^[\d\.,\s]+$", clean_text):
            val = float(clean_text.replace(",", "").strip())
            return NormalizedArea(
                raw_string=area_text,
                raw_numeric=val,
                raw_unit=None,
                normalized_sqm=None,
                normalized_acres=None,
                normalized_decimals=None,
                conversion_rule="MISSING_UNIT: Cannot infer area unit without explicit source confirmation",
                is_uncertain=True
            )

        # Check for composite Hindi / English expression: "X Acre Y Decimal" or "X एकड़ Y डिसमिल"
        m_comp_ad = re.search(r"(\d+(?:\.\d+)?)\s*(?:acre|एकड़)\s*(?:and\s*)?(\d+(?:\.\d+)?)\s*(?:dec|decimal|डिसमिल|डीसमिल)", clean_text)
        if m_comp_ad:
            ac_val = float(m_comp_ad.group(1))
            dec_val = float(m_comp_ad.group(2))
            sqm = (ac_val * cls.SQM_PER_ACRE) + (dec_val * cls.SQM_PER_DECIMAL)
            acres = sqm / cls.SQM_PER_ACRE
            decimals = sqm / cls.SQM_PER_DECIMAL
            return NormalizedArea(
                raw_string=area_text,
                raw_numeric=ac_val,
                raw_unit="acre_decimal_composite",
                normalized_sqm=sqm,
                normalized_acres=acres,
                normalized_decimals=decimals,
                conversion_rule="1 Acre = 4046.8564 SQM + 1 Decimal = 40.468564 SQM",
                is_uncertain=False
            )

        # Check for composite Bigha-Katha expression: "X Bigha Y Katha" or "X बीघा Y कट्ठा"
        m_comp_bk = re.search(r"(\d+(?:\.\d+)?)\s*(?:bigha|बीघा)\s*(?:and\s*)?(\d+(?:\.\d+)?)\s*(?:katha|kattha|कट्ठा|कठा)", clean_text)
        if m_comp_bk:
            bigha_val = float(m_comp_bk.group(1))
            katha_val = float(m_comp_bk.group(2))
            sqm = (bigha_val * cls.SQM_PER_BIGHA) + (katha_val * cls.SQM_PER_KATHA)
            acres = sqm / cls.SQM_PER_ACRE
            decimals = sqm / cls.SQM_PER_DECIMAL
            return NormalizedArea(
                raw_string=area_text,
                raw_numeric=bigha_val,
                raw_unit="bigha_katha_composite",
                normalized_sqm=sqm,
                normalized_acres=acres,
                normalized_decimals=decimals,
                conversion_rule="1 Bigha = 2529.285 SQM + 1 Katha = 126.46 SQM",
                is_uncertain=False
            )

        # Single unit regex supporting English and Devanagari Unicode
        match = re.search(r"([\d\.,]+)\s*([a-zA-Z\.\s\u0900-\u097f]+)", clean_text)
        if not match:
            return NormalizedArea(
                raw_string=area_text,
                raw_numeric=None,
                raw_unit=None,
                normalized_sqm=None,
                normalized_acres=None,
                normalized_decimals=None,
                conversion_rule="UNPARSABLE_AREA_STRING",
                is_uncertain=True
            )

        val_str, unit_raw = match.groups()
        try:
            val = float(val_str.replace(",", "").strip())
        except ValueError:
            return None

        unit = unit_raw.strip().replace(".", "")

        if any(w in unit for w in ["acre", "एकड़", "एकड"]):
            sqm = val * cls.SQM_PER_ACRE
            rule = "1 Acre = 4046.8564 SQM"
            unit_norm = "acre"
            uncertain = False
        elif any(w in unit for w in ["dec", "डिसमिल", "डीसमिल", "डेसिमल", "डिस"]):
            sqm = val * cls.SQM_PER_DECIMAL
            rule = "1 Decimal = 40.468564 SQM"
            unit_norm = "decimal"
            uncertain = False
        elif any(w in unit for w in ["katha", "kattha", "कट्ठा", "कठा", "कट्टा"]):
            sqm = val * cls.SQM_PER_KATHA
            rule = "1 Katha = 126.46 SQM (Standard Regional)"
            unit_norm = "katha"
            uncertain = False
        elif any(w in unit for w in ["bigha", "बीघा"]):
            sqm = val * cls.SQM_PER_BIGHA
            rule = "1 Bigha = 20 Katha = 2529.285 SQM"
            unit_norm = "bigha"
            uncertain = False
        elif any(w in unit for w in ["hectare", "हेक्टेयर", "हेक्टेअर", "ha"]):
            sqm = val * cls.SQM_PER_HECTARE
            rule = "1 Hectare = 10000.0 SQM"
            unit_norm = "hectare"
            uncertain = False
        elif ("sq" in unit and ("ft" in unit or "feet" in unit)) or "वर्ग फुट" in unit or "वर्ग फीट" in unit:
            sqm = val * cls.SQM_PER_SQFT
            rule = "1 Sq Ft = 0.092903 SQM"
            unit_norm = "sqft"
            uncertain = False
        elif "sqm" in unit or "square meter" in unit or "वर्ग मीटर" in unit:
            sqm = val
            rule = "1 SQM = 1 SQM (Identity)"
            unit_norm = "sqm"
            uncertain = False
        else:
            return NormalizedArea(
                raw_string=area_text,
                raw_numeric=val,
                raw_unit=unit,
                normalized_sqm=None,
                normalized_acres=None,
                normalized_decimals=None,
                conversion_rule=f"UNRECOGNIZED_UNIT: '{unit}'",
                is_uncertain=True
            )

        acres = sqm / cls.SQM_PER_ACRE
        decimals = sqm / cls.SQM_PER_DECIMAL

        return NormalizedArea(
            raw_string=area_text,
            raw_numeric=val,
            raw_unit=unit_norm,
            normalized_sqm=sqm,
            normalized_acres=acres,
            normalized_decimals=decimals,
            conversion_rule=rule,
            is_uncertain=uncertain
        )

    @classmethod
    def normalize_person_name(cls, name_text: str) -> NormalizedPersonName:
        if not name_text:
            return NormalizedPersonName(raw_string="", clean_name="")

        raw_str = name_text.strip()
        working = raw_str

        # Extract relationship patterns: S/o, W/o, D/o, C/o, पुत्र, पत्नी, पिता
        rel_prefix = None
        rel_name = None

        rel_match = re.search(r",?\s*(s/o|w/o|d/o|c/o|son of|wife of|daughter of|आत्मज)\s+([^,]+)", working, re.IGNORECASE)
        if rel_match:
            rel_prefix = rel_match.group(1).upper()
            rel_name = rel_match.group(2).strip()
            working = working[:rel_match.start()].strip()

        # Extract honorifics: Sri, Shri, Smt, Late, Mr, Mrs, डॉ
        honorific = None
        hon_match = re.match(r"^(shri|sri|smt|smti|late|mr|mrs|md|mohd|dr)\.?\s+(.+)$", working, re.IGNORECASE)
        if hon_match:
            honorific = hon_match.group(1).capitalize()
            clean_name = hon_match.group(2).strip()
        else:
            clean_name = working.strip()

        return NormalizedPersonName(
            raw_string=raw_str,
            clean_name=clean_name,
            relationship_prefix=rel_prefix,
            relative_name=rel_name,
            honorific=honorific
        )
