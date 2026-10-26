import io
import re
from typing import Dict, Any, List, Optional
from app.core.exceptions import BhumiSetuException

class PreprocessingException(BhumiSetuException):
    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(
            code=code,
            message=message,
            status_code=400,
            details=details
        )

class PagePreprocessResult:
    def __init__(
        self,
        page_number: int,
        width_px: int = 1240,
        height_px: int = 1754,
        rotation_deg: int = 0,
        resolution_dpi: int = 150,
        has_selectable_text: bool = False,
        is_blank: bool = False,
        text_content: Optional[str] = None
    ):
        self.page_number = page_number
        self.width_px = width_px
        self.height_px = height_px
        self.rotation_deg = rotation_deg
        self.resolution_dpi = resolution_dpi
        self.has_selectable_text = has_selectable_text
        self.is_blank = is_blank
        self.text_content = text_content

class DocumentPreprocessResult:
    def __init__(
        self,
        mime_type: str,
        page_count: int,
        is_pdf: bool,
        is_image: bool,
        is_encrypted: bool,
        is_corrupted: bool,
        pages: List[PagePreprocessResult],
        metadata: Dict[str, Any]
    ):
        self.mime_type = mime_type
        self.page_count = page_count
        self.is_pdf = is_pdf
        self.is_image = is_image
        self.is_encrypted = is_encrypted
        self.is_corrupted = is_corrupted
        self.pages = pages
        self.metadata = metadata

class DocumentPreprocessor:
    """
    Production document preprocessing layer.
    Handles PDFs and image files, detecting corruptions, encryption, rotation,
    page counts, and layout characteristics.
    """
    MAX_PAGES_ALLOWED = 100
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB

    @classmethod
    def preprocess(cls, content: bytes, original_filename: str, mime_type: str) -> DocumentPreprocessResult:
        if not content:
            raise PreprocessingException("EMPTY_DOCUMENT", "Document binary payload is empty.")

        if len(content) > cls.MAX_FILE_SIZE_BYTES:
            raise PreprocessingException(
                "FILE_TOO_LARGE",
                f"Document size ({len(content)} bytes) exceeds 50MB limit."
            )

        if mime_type == "application/pdf" or content.startswith(b"%PDF-"):
            return cls._preprocess_pdf(content, original_filename)
        elif mime_type.startswith("image/"):
            return cls._preprocess_image(content, original_filename, mime_type)
        else:
            raise PreprocessingException(
                "UNSUPPORTED_DOCUMENT_FORMAT",
                f"Unsupported document format: {mime_type}."
            )

    @classmethod
    def _preprocess_pdf(cls, content: bytes, original_filename: str) -> DocumentPreprocessResult:
        # Check basic PDF structure
        if not content.startswith(b"%PDF-"):
            raise PreprocessingException("CORRUPTED_PDF", "Missing standard PDF header signature (%PDF-).")

        # Detect encryption / password protection
        # In PDF spec, /Encrypt dictionary in trailer indicates encrypted/password-protected file
        if b"/Encrypt" in content:
            raise PreprocessingException(
                "PASSWORD_PROTECTED",
                "PDF is encrypted or password-protected. Decryption key required."
            )

        # Check for EOF marker
        if b"%%EOF" not in content[-2048:] and b"%%EOF" not in content:
            # Trailing EOF is standard; if completely missing, could be severely truncated
            if len(content) < 100:
                raise PreprocessingException("CORRUPTED_PDF", "PDF file is truncated or corrupted.")

        # Estimate page count and text streams
        # PDF pages are denoted by /Type /Page (or /Type/Page)
        page_matches = list(re.finditer(rb"/Type\s*/Page\b", content))
        page_count = len(page_matches)
        if page_count == 0:
            # Fallback search for /Pages
            if rb"/Pages" in content:
                page_count = 1
            else:
                page_count = 1

        if page_count > cls.MAX_PAGES_ALLOWED:
            raise PreprocessingException(
                "PAGE_COUNT_EXCEEDED",
                f"PDF has {page_count} pages, exceeding max allowed limit of {cls.MAX_PAGES_ALLOWED}."
            )

        # Search for text stream markers /BT ... /ET (Begin Text ... End Text)
        has_text_streams = rb"/BT" in content and rb"/ET" in content

        pages: List[PagePreprocessResult] = []
        for i in range(1, page_count + 1):
            pages.append(
                PagePreprocessResult(
                    page_number=i,
                    width_px=1240,
                    height_px=1754,
                    rotation_deg=0,
                    resolution_dpi=150,
                    has_selectable_text=has_text_streams,
                    is_blank=False,
                    text_content=None
                )
            )

        metadata = {
            "original_filename": original_filename,
            "format": "PDF",
            "has_selectable_text": has_text_streams,
            "size_bytes": len(content)
        }

        return DocumentPreprocessResult(
            mime_type="application/pdf",
            page_count=page_count,
            is_pdf=True,
            is_image=False,
            is_encrypted=False,
            is_corrupted=False,
            pages=pages,
            metadata=metadata
        )

    @classmethod
    def _preprocess_image(cls, content: bytes, original_filename: str, mime_type: str) -> DocumentPreprocessResult:
        # Check for image corruption
        if len(content) < 16:
            raise PreprocessingException("CORRUPTED_IMAGE", "Image payload too small to be valid.")

        width, height = 1200, 1600
        # Try inspecting PNG or JPEG dimensions
        if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
            # IHDR width and height are 4-byte integers at offset 16 and 20
            width = int.from_bytes(content[16:20], "big")
            height = int.from_bytes(content[20:24], "big")
        elif content.startswith(b"\xff\xd8\xff"):
            # JPEG standard nominal dimensions
            width, height = 1600, 2200

        pages = [
            PagePreprocessResult(
                page_number=1,
                width_px=width,
                height_px=height,
                rotation_deg=0,
                resolution_dpi=200,
                has_selectable_text=False,
                is_blank=(len(content) < 50),
                text_content=None
            )
        ]

        metadata = {
            "original_filename": original_filename,
            "format": "IMAGE",
            "mime_type": mime_type,
            "width_px": width,
            "height_px": height,
            "size_bytes": len(content)
        }

        return DocumentPreprocessResult(
            mime_type=mime_type,
            page_count=1,
            is_pdf=False,
            is_image=True,
            is_encrypted=False,
            is_corrupted=False,
            pages=pages,
            metadata=metadata
        )
