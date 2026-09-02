from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from app.models.document import ParsedDocument


class DocumentProcessingError(Exception):
    """Raised when a document cannot be parsed or processed."""
    pass


class BaseDocumentParser(ABC):
    """Abstract base class for format-specific document parsers."""

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        filename: str,
        mime_type: str,
        attachment_id: str,
    ) -> ParsedDocument:
        """Parse file content into a normalized ParsedDocument representation."""
        pass

    @staticmethod
    def read_text_safely(file_path: Path) -> str:
        """
        Reads text content trying common encodings (UTF-8, UTF-8-sig, CP1252, Latin-1).
        """
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
        raw_bytes = file_path.read_bytes()

        for enc in encodings:
            try:
                return raw_bytes.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue

        # Fallback with replacement
        return raw_bytes.decode("utf-8", errors="replace")

    @staticmethod
    def get_current_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()
