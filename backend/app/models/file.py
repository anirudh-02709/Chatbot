from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

AttachmentStatus = Literal["pending", "uploading", "uploaded", "error"]


class Attachment(BaseModel):
    id: str
    name: str
    size: int
    mime_type: str = Field(..., alias="mimeType", serialization_alias="mimeType")
    status: AttachmentStatus = "uploaded"
    uploaded_at: Optional[str] = Field(default=None, alias="uploadedAt", serialization_alias="uploadedAt")
    error_detail: Optional[str] = Field(default=None, alias="errorDetail", serialization_alias="errorDetail")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )


class FileConfigResponse(BaseModel):
    max_upload_size_bytes: int = Field(..., alias="maxUploadSizeBytes", serialization_alias="maxUploadSizeBytes")
    max_upload_size_mb: int = Field(..., alias="maxUploadSizeMb", serialization_alias="maxUploadSizeMb")
    allowed_extensions: list[str] = Field(..., alias="allowedExtensions", serialization_alias="allowedExtensions")
    allowed_mime_types: list[str] = Field(..., alias="allowedMimeTypes", serialization_alias="allowedMimeTypes")

    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
    )
