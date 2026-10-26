"""
Kaithi Script Unicode Mapping and Bihar Revenue Lexicon Reference
Unicode Block: U+11080 - U+110CF (Unicode 5.2+)
Standard: ISO/IEC 10646

Provides:
- Exact Unicode code point mappings for Kaithi consonants, vowels, matras, digits, and signs.
- Phonetic mapping to standard Devanagari (Hindi) and Latin (IAST).
- Standard historical Bihar Cadastral Survey (CS) revenue lexicon and abbreviations.
"""

from typing import Dict, Any, Optional, List, Tuple

# Kaithi Unicode Character Map (U+11080 - U+110CF)
KAITHI_CHARACTER_MAP: Dict[str, Dict[str, Any]] = {
    # Independent Vowels
    "\U00011083": {"name": "KAITHI LETTER A", "devanagari": "अ", "iast": "a", "category": "VOWEL"},
    "\U00011084": {"name": "KAITHI LETTER AA", "devanagari": "आ", "iast": "ā", "category": "VOWEL"},
    "\U00011085": {"name": "KAITHI LETTER I", "devanagari": "इ", "iast": "i", "category": "VOWEL"},
    "\U00011086": {"name": "KAITHI LETTER II", "devanagari": "ई", "iast": "ī", "category": "VOWEL"},
    "\U00011087": {"name": "KAITHI LETTER U", "devanagari": "उ", "iast": "u", "category": "VOWEL"},
    "\U00011088": {"name": "KAITHI LETTER UU", "devanagari": "ऊ", "iast": "ū", "category": "VOWEL"},
    "\U00011089": {"name": "KAITHI LETTER E", "devanagari": "ए", "iast": "e", "category": "VOWEL"},
    "\U0001108A": {"name": "KAITHI LETTER AI", "devanagari": "ऐ", "iast": "ai", "category": "VOWEL"},
    "\U0001108B": {"name": "KAITHI LETTER O", "devanagari": "ओ", "iast": "o", "category": "VOWEL"},
    "\U0001108C": {"name": "KAITHI LETTER AU", "devanagari": "औ", "iast": "au", "category": "VOWEL"},

    # Consonants
    "\U0001108D": {"name": "KAITHI LETTER KA", "devanagari": "क", "iast": "ka", "category": "CONSONANT"},
    "\U0001108E": {"name": "KAITHI LETTER KHA", "devanagari": "ख", "iast": "kha", "category": "CONSONANT"},
    "\U0001108F": {"name": "KAITHI LETTER GA", "devanagari": "ग", "iast": "ga", "category": "CONSONANT"},
    "\U00011090": {"name": "KAITHI LETTER GHA", "devanagari": "घ", "iast": "gha", "category": "CONSONANT"},
    "\U00011091": {"name": "KAITHI LETTER NGA", "devanagari": "ङ", "iast": "ṅa", "category": "CONSONANT"},
    "\U00011092": {"name": "KAITHI LETTER CA", "devanagari": "च", "iast": "ca", "category": "CONSONANT"},
    "\U00011093": {"name": "KAITHI LETTER CHA", "devanagari": "छ", "iast": "cha", "category": "CONSONANT"},
    "\U00011094": {"name": "KAITHI LETTER JA", "devanagari": "ज", "iast": "ja", "category": "CONSONANT"},
    "\U00011095": {"name": "KAITHI LETTER JHA", "devanagari": "झ", "iast": "jha", "category": "CONSONANT"},
    "\U00011096": {"name": "KAITHI LETTER NYA", "devanagari": "ञ", "iast": "ña", "category": "CONSONANT"},
    "\U00011097": {"name": "KAITHI LETTER TTA", "devanagari": "ट", "iast": "ṭa", "category": "CONSONANT"},
    "\U00011098": {"name": "KAITHI LETTER TTHA", "devanagari": "ठ", "iast": "ṭha", "category": "CONSONANT"},
    "\U00011099": {"name": "KAITHI LETTER DDA", "devanagari": "ड", "iast": "ḍa", "category": "CONSONANT"},
    "\U0001109A": {"name": "KAITHI LETTER DDDHA", "devanagari": "ड़", "iast": "ṛa", "category": "CONSONANT"},
    "\U0001109B": {"name": "KAITHI LETTER DDHA", "devanagari": "ढ", "iast": "ḍha", "category": "CONSONANT"},
    "\U0001109C": {"name": "KAITHI LETTER RHA", "devanagari": "ढ़", "iast": "ṛha", "category": "CONSONANT"},
    "\U0001109D": {"name": "KAITHI LETTER NNA", "devanagari": "ण", "iast": "ṇa", "category": "CONSONANT"},
    "\U0001109E": {"name": "KAITHI LETTER TA", "devanagari": "त", "iast": "ta", "category": "CONSONANT"},
    "\U0001109F": {"name": "KAITHI LETTER THA", "devanagari": "थ", "iast": "tha", "category": "CONSONANT"},
    "\U000110A0": {"name": "KAITHI LETTER DA", "devanagari": "द", "iast": "da", "category": "CONSONANT"},
    "\U000110A1": {"name": "KAITHI LETTER DHA", "devanagari": "ध", "iast": "dha", "category": "CONSONANT"},
    "\U000110A2": {"name": "KAITHI LETTER NA", "devanagari": "न", "iast": "na", "category": "CONSONANT"},
    "\U000110A3": {"name": "KAITHI LETTER PA", "devanagari": "प", "iast": "pa", "category": "CONSONANT"},
    "\U000110A4": {"name": "KAITHI LETTER PHA", "devanagari": "फ", "iast": "pha", "category": "CONSONANT"},
    "\U000110A5": {"name": "KAITHI LETTER BA", "devanagari": "ब", "iast": "ba", "category": "CONSONANT"},
    "\U000110A6": {"name": "KAITHI LETTER BHA", "devanagari": "भ", "iast": "bha", "category": "CONSONANT"},
    "\U000110A7": {"name": "KAITHI LETTER MA", "devanagari": "म", "iast": "ma", "category": "CONSONANT"},
    "\U000110A8": {"name": "KAITHI LETTER YA", "devanagari": "य", "iast": "ya", "category": "CONSONANT"},
    "\U000110A9": {"name": "KAITHI LETTER RA", "devanagari": "र", "iast": "ra", "category": "CONSONANT"},
    "\U000110AA": {"name": "KAITHI LETTER LA", "devanagari": "ल", "iast": "la", "category": "CONSONANT"},
    "\U000110AB": {"name": "KAITHI LETTER VA", "devanagari": "व", "iast": "va", "category": "CONSONANT"},
    "\U000110AC": {"name": "KAITHI LETTER SHA", "devanagari": "श", "iast": "śa", "category": "CONSONANT"},
    "\U000110AD": {"name": "KAITHI LETTER SSA", "devanagari": "ष", "iast": "ṣa", "category": "CONSONANT"},
    "\U000110AE": {"name": "KAITHI LETTER SA", "devanagari": "स", "iast": "sa", "category": "CONSONANT"},
    "\U000110AF": {"name": "KAITHI LETTER HA", "devanagari": "ह", "iast": "ha", "category": "CONSONANT"},

    # Dependent Vowel Signs (Matras)
    "\U000110B0": {"name": "KAITHI VOWEL SIGN AA", "devanagari": "ा", "iast": "ā", "category": "MATRA"},
    "\U000110B1": {"name": "KAITHI VOWEL SIGN I", "devanagari": "ि", "iast": "i", "category": "MATRA"},
    "\U000110B2": {"name": "KAITHI VOWEL SIGN II", "devanagari": "ी", "iast": "ī", "category": "MATRA"},
    "\U000110B3": {"name": "KAITHI VOWEL SIGN U", "devanagari": "ु", "iast": "u", "category": "MATRA"},
    "\U000110B4": {"name": "KAITHI VOWEL SIGN UU", "devanagari": "ू", "iast": "ū", "category": "MATRA"},
    "\U000110B5": {"name": "KAITHI VOWEL SIGN E", "devanagari": "े", "iast": "e", "category": "MATRA"},
    "\U000110B6": {"name": "KAITHI VOWEL SIGN AI", "devanagari": "ै", "iast": "ai", "category": "MATRA"},
    "\U000110B7": {"name": "KAITHI VOWEL SIGN O", "devanagari": "ो", "iast": "o", "category": "MATRA"},
    "\U000110B8": {"name": "KAITHI VOWEL SIGN AU", "devanagari": "ौ", "iast": "au", "category": "MATRA"},

    # Signs, Modifiers, and Virama
    "\U00011080": {"name": "KAITHI SIGN CANDRABINDU", "devanagari": "ँ", "iast": "m̐", "category": "SIGN"},
    "\U00011081": {"name": "KAITHI SIGN ANUSVARA", "devanagari": "ं", "iast": "ṃ", "category": "SIGN"},
    "\U00011082": {"name": "KAITHI SIGN VISARGA", "devanagari": "ः", "iast": "ḥ", "category": "SIGN"},
    "\U000110B9": {"name": "KAITHI SIGN VIRAMA", "devanagari": "्", "iast": "", "category": "SIGN"},
    "\U000110BA": {"name": "KAITHI SIGN NUKTA", "devanagari": "़", "iast": "", "category": "SIGN"},

    # Punctuation & Section Markers
    "\U000110BB": {"name": "KAITHI DANDA", "devanagari": "।", "iast": "|", "category": "PUNCTUATION"},
    "\U000110BC": {"name": "KAITHI DOUBLE DANDA", "devanagari": "॥", "iast": "||", "category": "PUNCTUATION"},
    "\U000110BD": {"name": "KAITHI NUMBER SIGN (RUPEE)", "devanagari": "रु०", "iast": "Rs.", "category": "CURRENCY"},
    "\U000110BE": {"name": "KAITHI NUMBER SIGN", "devanagari": "नं०", "iast": "No.", "category": "ABBREVIATION"},
    "\U000110BF": {"name": "KAITHI SECTION MARK", "devanagari": "§", "iast": "sec", "category": "PUNCTUATION"},
    "\U000110C0": {"name": "KAITHI DOUBLE SECTION MARK", "devanagari": "§§", "iast": "sec-sec", "category": "PUNCTUATION"},
    "\U000110C1": {"name": "KAITHI DANDA WITH DOUBLE CIRCLE", "devanagari": "०।०", "iast": "o|o", "category": "PUNCTUATION"},

    # Common Numerals (Mapped directly to Indic Digits)
    "०": {"name": "KAITHI DIGIT ZERO", "devanagari": "०", "iast": "0", "category": "DIGIT"},
    "१": {"name": "KAITHI DIGIT ONE", "devanagari": "१", "iast": "1", "category": "DIGIT"},
    "२": {"name": "KAITHI DIGIT TWO", "devanagari": "२", "iast": "2", "category": "DIGIT"},
    "३": {"name": "KAITHI DIGIT THREE", "devanagari": "३", "iast": "3", "category": "DIGIT"},
    "४": {"name": "KAITHI DIGIT FOUR", "devanagari": "४", "iast": "4", "category": "DIGIT"},
    "५": {"name": "KAITHI DIGIT FIVE", "devanagari": "५", "iast": "5", "category": "DIGIT"},
    "६": {"name": "KAITHI DIGIT SIX", "devanagari": "६", "iast": "6", "category": "DIGIT"},
    "७": {"name": "KAITHI DIGIT SEVEN", "devanagari": "७", "iast": "7", "category": "DIGIT"},
    "८": {"name": "KAITHI DIGIT EIGHT", "devanagari": "८", "iast": "8", "category": "DIGIT"},
    "९": {"name": "KAITHI DIGIT NINE", "devanagari": "९", "iast": "9", "category": "DIGIT"},
}

# Inverted mapping: Devanagari to Kaithi character
DEV_TO_KAITHI: Dict[str, str] = {
    meta["devanagari"]: char
    for char, meta in KAITHI_CHARACTER_MAP.items()
    if meta["category"] in ("VOWEL", "CONSONANT", "MATRA", "SIGN", "PUNCTUATION")
}

# Historical Bihar Land & Revenue Lexicon Dictionary
# Used for spell-checking, lexicon matching, and disambiguation in Cadastral records
BIHAR_REVENUE_LEXICON: Dict[str, Dict[str, Any]] = {
    "KHATIYAN": {
        "devanagari": "खतियान",
        "kaithi": "\U0001108E\U0001109E\U000110B1\U00011084\U000110A2",  # ख + त + ि + आ + न
        "english": "Record of Rights / Khatiyan",
        "category": "DOCUMENT_TYPE"
    },
    "KHESRA": {
        "devanagari": "खेसरा",
        "kaithi": "\U0001108E\U000110B5\U000110AE\U000110A9\U000110B0",  # ख + े + स + र + ा
        "english": "Survey Plot / Khesra Number",
        "category": "FIELD_HEADER"
    },
    "KHATA": {
        "devanagari": "खाता",
        "kaithi": "\U0001108E\U000110B0\U0001109E\U000110B0",  # ख + ा + त + ा
        "english": "Khata / Holding Number",
        "category": "FIELD_HEADER"
    },
    "MAUZA": {
        "devanagari": "मौजा",
        "kaithi": "\U000110A7\U000110B8\U00011094\U000110B0",  # म + ौ + ज + ा
        "english": "Revenue Village / Mauza",
        "category": "LOCATION"
    },
    "THANA": {
        "devanagari": "थाना",
        "kaithi": "\U0001109F\U000110B0\U000110A2\U000110B0",  # थ + ा + न + ा
        "english": "Police Station / Revenue Jurisdiction",
        "category": "LOCATION"
    },
    "RAIYAT": {
        "devanagari": "रैयत",
        "kaithi": "\U000110A9\U000110B6\U000110A8\U0001109E",  # र + ै + य + त
        "english": "Recorded Tenant / Raiyat",
        "category": "ENTITY"
    },
    "RAKBA": {
        "devanagari": "रकबा",
        "kaithi": "\U000110A9\U0001108D\U000110A5\U000110B0",  # र + क + ब + ा
        "english": "Recorded Area / Rakba",
        "category": "MEASUREMENT"
    },
    "LAGAN": {
        "devanagari": "लगान",
        "kaithi": "\U000110AA\U0001108F\U000110B0\U000110A2",  # ल + ग + ा + न
        "english": "Annual Rent / Revenue Demand",
        "category": "FINANCIAL"
    },
    "CHAUSIMA": {
        "devanagari": "चौहद्दी",
        "kaithi": "\U00011092\U000110B8\U000110AF\U000110A0\U000110A0\U000110B2",  # च + ौ + ह + द + द + ी
        "english": "Four-Directional Boundaries",
        "category": "SPATIAL"
    },
    "UTTAR": {
        "devanagari": "उत्तर",
        "kaithi": "\U00011087\U0001109E\U0001109E\U000110A9",  # उ + त + त + र
        "english": "North",
        "category": "DIRECTION"
    },
    "DAKSHIN": {
        "devanagari": "दक्षिण",
        "kaithi": "\U000110A0\U0001108D\U000110AD\U000110B1\U000110A2",  # द + क + ष + ि + ण
        "english": "South",
        "category": "DIRECTION"
    },
    "PURAB": {
        "devanagari": "पूरब",
        "kaithi": "\U000110A3\U000110B4\U000110A9\U000110A5",  # प + ू + र + ब
        "english": "East",
        "category": "DIRECTION"
    },
    "PASHCHIM": {
        "devanagari": "पश्चिम",
        "kaithi": "\U000110A3\U000110AC\U00011092\U000110B1\U000110A7",  # प + श + च + ि + म
        "english": "West",
        "category": "DIRECTION"
    },
    "DHANI": {
        "devanagari": "धनी",
        "kaithi": "\U000110A1\U000110A2\U000110B2",  # ध + न + ी
        "english": "Paddy Land (Class 1 or 2)",
        "category": "LAND_NATURE"
    },
    "BHITH": {
        "devanagari": "भीठ",
        "kaithi": "\U000110A6\U000110B2\U00011098",  # भ + ी + ठ
        "english": "Highland / Upland for rabi crops",
        "category": "LAND_NATURE"
    },
    "BAKASHT": {
        "devanagari": "बकाश्त",
        "kaithi": "\U000110A5\U0001108D\U000110B0\U000110AC\U0001109E",  # ब + क + ा + श + त
        "english": "Land held directly in personal cultivation of landlord",
        "category": "TENURE"
    },
    "GAIR_MAZRUA": {
        "devanagari": "गैरमजरूआ",
        "kaithi": "\U0001108F\U000110B6\U000110A9\U000110A7\U00011094\U000110A9\U000110B4\U00011084",  # ग + ै + र + म + ज + र + ू + आ
        "english": "Uncultivated / Public or Landlord Common Land",
        "category": "TENURE"
    }
}

# Common Historical Confusion Pairs for Kaithi
KAITHI_CONFUSION_PAIRS = [
    ("\U0001108D", "\U000110A5"),  # KA vs BA
    ("\U000110A9", "\U000110AE"),  # RA vs SA
    ("\U000110AA", "\U0001109E"),  # LA vs TA
    ("\U000110A8", "\U00011094"),  # YA vs JA
    ("\U0001108E", "\U000110A9"),  # KHA vs RA
]
