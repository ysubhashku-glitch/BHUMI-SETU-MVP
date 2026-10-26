from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import uuid

class DocumentProcessor(ABC):
    """
    Phase 3 boundary interface for asynchronous multi-page document processing
    (PDF rasterization, OCR text extraction, layout analysis).
    """
    @abstractmethod
    def process_document(self, document_id: uuid.UUID, storage_uri: str) -> Dict[str, Any]:
        """Dispatches document to OCR/Vision pipeline. Returns processing job metadata."""
        pass

class DocumentParser(ABC):
    """
    Phase 3 boundary interface for parsing extracted text into structured records
    (Registered Deeds, Khatiyan pages, Jamabandi Panji II extracts).
    """
    @abstractmethod
    def parse_extracted_text(self, document_id: uuid.UUID, text_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parses extracted OCR text into typed legal/revenue entities."""
        pass

class EvidenceExtractor(ABC):
    """
    Phase 3 boundary interface for converting parsed document segments into verified Evidence artifacts.
    """
    @abstractmethod
    def extract_evidence(self, parsed_payload: Dict[str, Any], document_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Extracts candidate Evidence items with provenance, authority tier, and confidence score."""
        pass

class ClaimCandidateGenerator(ABC):
    """
    Phase 3 boundary interface for generating atomic Claim candidates from extracted Evidence.
    """
    @abstractmethod
    def generate_candidate_claims(self, evidence_id: uuid.UUID, evidence_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generates Subject-Predicate-Object claims ready for consistency evaluation."""
        pass
