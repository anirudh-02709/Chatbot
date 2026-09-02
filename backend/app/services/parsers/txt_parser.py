from pathlib import Path
from app.models.document import ParsedDocument, DocumentSection
from app.services.parsers.base import BaseDocumentParser, DocumentProcessingError


class TxtParser(BaseDocumentParser):
    """Parser for plain text files (.txt)."""

    def parse(
        self,
        file_path: Path,
        filename: str,
        mime_type: str,
        attachment_id: str,
    ) -> ParsedDocument:
        try:
            content = self.read_text_safely(file_path)
        except Exception as e:
            raise DocumentProcessingError(f"Failed to read text file: {e}")

        clean_text = content.strip()
        file_size = file_path.stat().st_size if file_path.exists() else len(content.encode("utf-8"))

        # If text is substantial, split into paragraphs or keep as cohesive section
        paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]

        sections: list[DocumentSection] = []
        if paragraphs:
            # Group into logical sections (e.g. paragraphs or single block)
            for idx, para in enumerate(paragraphs):
                sections.append(
                    DocumentSection(
                        index=idx,
                        title=f"Paragraph {idx + 1}" if len(paragraphs) > 1 else None,
                        content=para,
                        page_number=1,
                        character_count=len(para),
                        metadata={"format": "txt"},
                    )
                )
        else:
            sections.append(
                DocumentSection(
                    index=0,
                    title=None,
                    content="",
                    page_number=1,
                    character_count=0,
                    metadata={"format": "txt"},
                )
            )

        return ParsedDocument(
            attachment_id=attachment_id,
            filename=filename,
            mime_type=mime_type or "text/plain",
            size=file_size,
            status="processed",
            total_characters=len(clean_text),
            page_count=1,
            section_count=len(sections),
            processed_at=self.get_current_timestamp(),
            sections=sections,
            metadata={"format": "txt", "paragraph_count": len(paragraphs)},
        )
