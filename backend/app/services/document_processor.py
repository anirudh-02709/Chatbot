import logging
import re
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, status

from app.config import Settings, get_settings
from app.models.document import ParsedDocument
from app.services.parsers.base import DocumentProcessingError
from app.services.parsers.registry import parser_registry, DocumentParserRegistry

logger = logging.getLogger("chatbot.document_processor")


class DocumentProcessingService:
    """Service to locate, validate, and parse uploaded documents."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        registry: Optional[DocumentParserRegistry] = None,
    ):
        self.settings = settings or get_settings()
        self.registry = registry or parser_registry
        backend_root = Path(__file__).resolve().parent.parent.parent
        self.storage_path = (backend_root / self.settings.upload_dir).resolve()

    def find_attachment_file(self, attachment_id: str) -> Path:
        """
        Locates the physical file for an attachment ID within the storage boundary.
        Prevents path traversal and verifies existence.
        """
        # Validate attachment_id format
        if not re.match(r"^att_[a-zA-Z0-9]+$", attachment_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid attachment ID format.",
            )

        if not self.storage_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment storage directory not found.",
            )

        # Match files starting with attachment_id
        candidates = list(self.storage_path.glob(f"{attachment_id}.*"))
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment '{attachment_id}' not found.",
            )

        target_file = candidates[0].resolve()

        # Strict anti-path traversal check
        if not str(target_file).startswith(str(self.storage_path)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file location.",
            )

        if not target_file.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment file for '{attachment_id}' does not exist.",
            )

        return target_file

    def get_mime_type_from_ext(self, ext: str) -> str:
        """Derive standard MIME type from extension."""
        ext_mime_map = {
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".json": "application/json",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        return ext_mime_map.get(ext.lower(), "application/octet-stream")

    def process_attachment(self, attachment_id: str) -> ParsedDocument:
        """
        Locates the attachment, selects the appropriate parser, and extracts text/sections.
        """
        file_path = self.find_attachment_file(attachment_id)
        ext = file_path.suffix.lower()
        mime_type = self.get_mime_type_from_ext(ext)

        parser = self.registry.get_parser(ext, mime_type)
        if not parser:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No parser available for file format '{ext}'.",
            )

        try:
            logger.info(f"Parsing attachment {attachment_id} ({ext}) using {parser.__class__.__name__}")
            parsed_doc = parser.parse(
                file_path=file_path,
                filename=file_path.name,
                mime_type=mime_type,
                attachment_id=attachment_id,
            )
            logger.info(
                f"Successfully parsed {attachment_id}: {parsed_doc.section_count} sections, {parsed_doc.total_characters} chars"
            )
            return parsed_doc

        except DocumentProcessingError as dpe:
            raw_err = str(dpe)
            # Remove any storage paths if present in error message
            clean_err = raw_err.replace(str(self.storage_path), "").replace(str(file_path), file_path.name)
            logger.warning(f"Document processing failed for {attachment_id}: {clean_err}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=clean_err,
            )
        except Exception as e:
            logger.error(f"Unexpected error processing document {attachment_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while parsing the document.",
            )
