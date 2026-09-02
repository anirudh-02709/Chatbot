from pathlib import Path
import pypdf
from app.models.document import ParsedDocument, DocumentSection
from app.services.parsers.base import BaseDocumentParser, DocumentProcessingError


class PdfParser(BaseDocumentParser):
    """Parser for PDF documents (.pdf) using pypdf."""

    def parse(
        self,
        file_path: Path,
        filename: str,
        mime_type: str,
        attachment_id: str,
    ) -> ParsedDocument:
        file_size = file_path.stat().st_size if file_path.exists() else 0

        try:
            reader = pypdf.PdfReader(str(file_path))
        except pypdf.errors.PdfReadError as e:
            raise DocumentProcessingError(f"Corrupted or invalid PDF file: {e}")
        except Exception as e:
            raise DocumentProcessingError(f"Failed to read PDF file: {e}")

        if reader.is_encrypted:
            try:
                # Attempt decrypt with empty password
                reader.decrypt("")
            except Exception:
                raise DocumentProcessingError("PDF is password-protected and cannot be read.")

        num_pages = len(reader.pages)
        if num_pages == 0:
            raise DocumentProcessingError("PDF contains 0 pages.")

        sections: list[DocumentSection] = []
        total_extracted_chars = 0

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            try:
                extracted_text = page.extract_text() or ""
            except Exception as e:
                extracted_text = f"[Text extraction error on page {page_num}: {e}]"

            clean_page_text = extracted_text.strip()
            total_extracted_chars += len(clean_page_text)

            sections.append(
                DocumentSection(
                    index=page_idx,
                    title=f"Page {page_num}",
                    content=clean_page_text,
                    page_number=page_num,
                    character_count=len(clean_page_text),
                    metadata={"format": "pdf", "page": page_num, "total_pages": num_pages},
                )
            )

        return ParsedDocument(
            attachment_id=attachment_id,
            filename=filename,
            mime_type=mime_type or "application/pdf",
            size=file_size,
            status="processed",
            total_characters=total_extracted_chars,
            page_count=num_pages,
            section_count=len(sections),
            processed_at=self.get_current_timestamp(),
            sections=sections,
            metadata={"format": "pdf", "page_count": num_pages},
        )
