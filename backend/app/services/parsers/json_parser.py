import json
from pathlib import Path
from app.models.document import ParsedDocument, DocumentSection
from app.services.parsers.base import BaseDocumentParser, DocumentProcessingError


class JsonParser(BaseDocumentParser):
    """Parser for JSON documents (.json)."""

    def parse(
        self,
        file_path: Path,
        filename: str,
        mime_type: str,
        attachment_id: str,
    ) -> ParsedDocument:
        try:
            raw_content = self.read_text_safely(file_path)
        except Exception as e:
            raise DocumentProcessingError(f"Failed to read JSON file: {e}")

        file_size = file_path.stat().st_size if file_path.exists() else len(raw_content.encode("utf-8"))

        if not raw_content.strip():
            raise DocumentProcessingError("JSON file is empty.")

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as e:
            raise DocumentProcessingError(
                f"Invalid JSON syntax at line {e.lineno}, column {e.colno}: {e.msg}"
            )

        sections: list[DocumentSection] = []

        if isinstance(data, list):
            # If array of objects, split each top-level entry or chunk into structured sections
            for idx, item in enumerate(data):
                formatted = json.dumps(item, indent=2, ensure_ascii=False)
                item_title = None
                if isinstance(item, dict):
                    # Pick common title fields if available
                    for title_key in ["title", "name", "id", "key", "header"]:
                        if title_key in item and isinstance(item[title_key], (str, int)):
                            item_title = f"Item {idx + 1}: {item[title_key]}"
                            break
                sections.append(
                    DocumentSection(
                        index=idx,
                        title=item_title or f"Item {idx + 1}",
                        content=formatted,
                        page_number=1,
                        character_count=len(formatted),
                        metadata={"format": "json", "item_index": idx},
                    )
                )
        elif isinstance(data, dict):
            # If top-level object with keys, create section per top-level key or unified view
            if len(data) > 1:
                for idx, (key, value) in enumerate(data.items()):
                    formatted_val = json.dumps(value, indent=2, ensure_ascii=False)
                    section_content = f'"{key}": {formatted_val}'
                    sections.append(
                        DocumentSection(
                            index=idx,
                            title=f"Key: {key}",
                            content=section_content,
                            page_number=1,
                            character_count=len(section_content),
                            metadata={"format": "json", "key": key},
                        )
                    )
            else:
                formatted = json.dumps(data, indent=2, ensure_ascii=False)
                sections.append(
                    DocumentSection(
                        index=0,
                        title=None,
                        content=formatted,
                        page_number=1,
                        character_count=len(formatted),
                        metadata={"format": "json"},
                    )
                )
        else:
            # Primitive top-level value
            formatted = str(data)
            sections.append(
                DocumentSection(
                    index=0,
                    title=None,
                    content=formatted,
                    page_number=1,
                    character_count=len(formatted),
                    metadata={"format": "json"},
                )
            )

        total_chars = sum(s.character_count for s in sections)

        return ParsedDocument(
            attachment_id=attachment_id,
            filename=filename,
            mime_type=mime_type or "application/json",
            size=file_size,
            status="processed",
            total_characters=total_chars,
            page_count=1,
            section_count=len(sections),
            processed_at=self.get_current_timestamp(),
            sections=sections,
            metadata={"format": "json", "is_array": isinstance(data, list)},
        )
