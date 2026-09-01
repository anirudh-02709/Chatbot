from fastapi import APIRouter, Depends, File, UploadFile, status

from app.config import Settings, get_settings
from app.models.file import Attachment, FileConfigResponse
from app.services.file_storage import FileStorageService

router = APIRouter(prefix="/api/files", tags=["files"])


def get_file_storage_service(
    settings: Settings = Depends(get_settings),
) -> FileStorageService:
    return FileStorageService(settings=settings)


@router.post(
    "/upload",
    response_model=Attachment,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an attachment file",
    response_description="Attachment metadata after successful upload and validation",
)
async def upload_file(
    file: UploadFile = File(..., description="File to upload (PDF, TXT, MD, CSV, JSON, DOCX)"),
    storage_service: FileStorageService = Depends(get_file_storage_service),
):
    """
    Accepts a single file upload via multipart/form-data.
    Validates file extension, MIME type, size limit, and sanitizes filename.
    Stores the file in local storage and returns structured metadata.
    """
    return await storage_service.save_file(file)


@router.get(
    "/config",
    response_model=FileConfigResponse,
    summary="Get upload size limits and supported file extensions",
)
async def file_config(
    settings: Settings = Depends(get_settings),
):
    """
    Returns the supported extensions, MIME types, and max upload size limits.
    """
    max_mb = settings.max_upload_size_bytes // (1024 * 1024)
    return FileConfigResponse(
        max_upload_size_bytes=settings.max_upload_size_bytes,
        max_upload_size_mb=max_mb,
        allowed_extensions=settings.allowed_extensions,
        allowed_mime_types=settings.allowed_mime_types,
    )
