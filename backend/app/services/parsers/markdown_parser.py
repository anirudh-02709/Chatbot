import re
from pathlib import Path
from app.models.document import ParsedDocument, DocumentSection
from app.services.parsers.base import BaseDocumentParser, DocumentProcessingError


class MarkdownParser(BaseDocumentParser):
    """Parser for Markdown documents (.md)."""

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
            raise DocumentProcessingError(f"Failed to read Markdown file: {e}")

        clean_text = content.strip()
        file_size = file_path.stat().st_size if file_path.exists() else len(content.encode("utf-8"))

        # Split content based on markdown headers (# Header, ## Header, etc.)
        header_pattern = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)
        splits = header_pattern.split(clean_text)

        sections: list[DocumentSection] = []

        if len(splits) > 1:
            current_title = None
            current_text_parts: list[str] = []
            section_idx = 0

            for part in splits:
                part_stripped = part.strip()
                if not part_stripped:
                    continue

                if header_pattern.match(part_stripped):
                    # Save previous section if it has content
                    if current_text_parts or current_title:
                        body = "\n\n".join(current_text_parts).strip()
                        full_content = f"{current_title}\n\n{body}" if current_title and body else (current_title or body)
                        sections.append(
                            DocumentSection(
                                index=section_idx,
                                title=current_title,
                                content=full_content,
                                page_number=1,
                                character_count=len(full_content),
                                metadata={"format": "md", "heading": current_title},
                            )
                        )
                        section_idx += 1
                        current_text_parts = []
                    current_title = part_stripped
                else:
                    current_text_parts.append(part_stripped)

            # Append the final section
            if current_title or current_text_parts:
                body = "\n\n".join(current_text_parts).strip()
                full_content = f"{current_title}\n\n{body}" if current_title and body else (current_title or body)
                sections.append(
                    DocumentSection(
                        index=section_idx,
                        title=current_title,
                        content=full_content,
                        page_number=1,
                        character_count=len(full_content),
                        metadata={"format": "md", "heading": current_title},
                    )
                )
        else:
            # No headers, split by paragraphs
            paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
            if paragraphs:
                for idx, para in enumerate(paragraphs):
                    sections.append(
                        DocumentSection(
                            index=idx,
                            title=None,
                            content=para,
                            page_number=1,
                            character_count=len(para),
                            metadata={"format": "md"},
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
                        metadata={"format": "md"},
                    )
                )

        return ParsedDocument(
            attachment_id=attachment_id,
            filename=filename,
            mime_type=mime_type or "text/markdown",
            size=file_size,
            status="processed",
            total_characters=len(clean_text),
            page_count=1,
            section_count=len(sections),
            processed_at=self.get_current_timestamp(),
            sections=sections,
            metadata={"format": "md", "heading_count": len([s for s in sections if s.title])},
        )
