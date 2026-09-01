import os
import re
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException, status

from app.config import Settings, get_settings
from app.models.file import Attachment

logger = logging.getLogger("chatbot.file_storage")


class FileStorageService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        # Resolve storage directory relative to backend root
        backend_root = Path(__file__).resolve().parent.parent.parent
        self.storage_path = (backend_root / self.settings.upload_dir).resolve()
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Create storage directory if it does not exist."""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create storage directory {self.storage_path}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to initialize local storage directory.",
            )

    @staticmethod
    def sanitize_filename(filename: Optional[str]) -> str:
        """
        Sanitizes client-provided filename to prevent path traversal
        and remove dangerous characters.
        """
        if not filename:
            return "attachment.txt"

        # Remove null bytes and control characters
        clean = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)
        # Remove directory paths (both unix and windows)
        clean = os.path.basename(clean.replace("\\", "/"))
        # Strip leading/trailing spaces and dots
        clean = clean.strip(". ")
        # Separate base and extension
        base, ext = os.path.splitext(clean)
        # Remove unsafe characters from base, keeping alphanumeric, dots, dashes, underscores, and spaces
        base = re.sub(r"[^\w\.\-\s]", "_", base)
        # Collapse multiple dots into a single dot
        base = re.sub(r"\.+", ".", base)
        # Collapse multiple spaces or underscores
        base = re.sub(r"[\s_]+", "_", base)
        base = base.strip("._ ")

        ext = re.sub(r"[^\w\.]", "", ext).lower()

        if not base:
            base = "attachment"

        return f"{base}{ext}" if ext else base

    def validate_file_type(self, filename: str, content_type: Optional[str]) -> str:
        """
        Validates file extension and MIME type against configured whitelist.
        Returns the normalized extension.
        """
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{filename}' has no extension. Supported extensions: {', '.join(self.settings.allowed_extensions)}",
            )

        if ext not in [e.lower() for e in self.settings.allowed_extensions]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file extension '{ext}'. Supported extensions: {', '.join(self.settings.allowed_extensions)}",
            )

        # Basic MIME check if provided
        if content_type:
            normalized_mime = content_type.lower().split(";")[0].strip()
            # Explicitly block dangerous binary/executable mime types
            blocked_mime_prefixes = [
                "application/x-executable",
                "application/x-msdownload",
                "application/x-sh",
                "application/x-bat",
            ]
            for blocked in blocked_mime_prefixes:
                if normalized_mime.startswith(blocked):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Disallowed executable MIME type: {content_type}",
                    )

        return ext

    def get_mime_type(self, ext: str, provided_mime: Optional[str]) -> str:
        """Derive or normalize MIME type."""
        ext_mime_map = {
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
            ".json": "application/json",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        if provided_mime and provided_mime != "application/octet-stream":
            return provided_mime.split(";")[0].strip()
        return ext_mime_map.get(ext.lower(), "text/plain")

    async def save_file(self, file: UploadFile) -> Attachment:
        """
        Stream and save an uploaded file with size, type, and path traversal validation.
        """
        raw_filename = file.filename or "file"
        sanitized_name = self.sanitize_filename(raw_filename)
        ext = self.validate_file_type(sanitized_name, file.content_type)
        mime_type = self.get_mime_type(ext, file.content_type)

        # Generate unique attachment ID
        attachment_id = f"att_{uuid.uuid4().hex[:16]}"
        safe_stored_filename = f"{attachment_id}{ext}"
        destination_path = (self.storage_path / safe_stored_filename).resolve()

        # Enforce destination stays strictly within storage directory (anti-traversal)
        if not str(destination_path).startswith(str(self.storage_path)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path.",
            )

        total_bytes = 0
        chunk_size = 64 * 1024  # 64 KB chunks

        try:
            with open(destination_path, "wb") as buffer:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > self.settings.max_upload_size_bytes:
                        # Clean up oversized file
                        buffer.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        max_mb = self.settings.max_upload_size_bytes // (1024 * 1024)
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"File exceeds maximum allowed size of {max_mb} MB.",
                        )
                    buffer.write(chunk)

            if total_bytes == 0:
                if destination_path.exists():
                    destination_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot upload empty (0 byte) file.",
                )

            uploaded_at = datetime.now(timezone.utc).isoformat()
            logger.info(
                f"Stored attachment {attachment_id} ({sanitized_name}, {total_bytes} bytes)"
            )

            return Attachment(
                id=attachment_id,
                name=sanitized_name,
                size=total_bytes,
                mime_type=mime_type,
                status="uploaded",
                uploaded_at=uploaded_at,
            )

        except HTTPException:
            raise
        except Exception as e:
            if destination_path.exists():
                try:
                    destination_path.unlink()
                except Exception:
                    pass
            logger.error(f"Error saving upload {raw_filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded file.",
            )
        finally:
            await file.close()
