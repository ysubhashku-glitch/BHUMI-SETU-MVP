from typing import Optional
from app.models.evidence import DocumentCategory
from app.services.parsers.base_parser import DocumentParser, ParsedField, DocumentParseResult
from app.services.parsers.sale_deed_parser import SaleDeedParser
from app.services.parsers.khatiyan_parser import KhatiyanParser
from app.services.parsers.jamabandi_parser import JamabandiParser
from app.services.parsers.mutation_parser import MutationParser
from app.services.parsers.encumbrance_parser import EncumbranceParser

_PARSER_REGISTRY = {
    DocumentCategory.SALE_DEED: SaleDeedParser(),
    DocumentCategory.GIFT_DEED: SaleDeedParser(),
    DocumentCategory.PARTITION_DEED: SaleDeedParser(),
    DocumentCategory.KHATIYAN: KhatiyanParser(),
    DocumentCategory.JAMABANDI: JamabandiParser(),
    DocumentCategory.MUTATION_RECORD: MutationParser(),
    DocumentCategory.ENCUMBRANCE_CERTIFICATE: EncumbranceParser(),
}

def get_parser_for_category(category: str) -> DocumentParser:
    """Returns the specialized DocumentParser for a given document category."""
    return _PARSER_REGISTRY.get(category, SaleDeedParser())

__all__ = [
    "DocumentParser",
    "ParsedField",
    "DocumentParseResult",
    "SaleDeedParser",
    "KhatiyanParser",
    "JamabandiParser",
    "MutationParser",
    "EncumbranceParser",
    "get_parser_for_category"
]
