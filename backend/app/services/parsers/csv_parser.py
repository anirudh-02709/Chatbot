import csv
import io
from pathlib import Path
from app.models.document import ParsedDocument, DocumentSection
from app.services.parsers.base import BaseDocumentParser, DocumentProcessingError


class CsvParser(BaseDocumentParser):
    """Parser for CSV documents (.csv)."""

    def parse(
        self,
        file_path: Path,
        filename: str,
        mime_type: str,
        attachment_id: str,
    ) -> ParsedDocument:
        try:
            raw_text = self.read_text_safely(file_path)
        except Exception as e:
            raise DocumentProcessingError(f"Failed to read CSV file: {e}")

        file_size = file_path.stat().st_size if file_path.exists() else len(raw_text.encode("utf-8"))

        clean_text = raw_text.strip()
        if not clean_text:
            raise DocumentProcessingError("CSV file is empty.")

        # Detect delimiter safely
        delimiter = ","
        try:
            sample = clean_text[:2048]
            dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])
            delimiter = dialect.delimiter
        except Exception:
            # Fallback to comma
            delimiter = ","

        try:
            reader = csv.reader(io.StringIO(clean_text), delimiter=delimiter)
            rows = [row for row in reader if any(field.strip() for field in row)]
        except Exception as e:
            raise DocumentProcessingError(f"Malformed CSV content: {e}")

        if not rows:
            raise DocumentProcessingError("CSV contains no valid rows.")

        headers = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []

        # Create structured markdown table / rows
        sections: list[DocumentSection] = []
        rows_per_section = 25  # Group rows for clean sectioning

        if not data_rows:
            # Header only
            header_line = " | ".join(headers)
            content = f"| {header_line} |\n| {' | '.join(['---'] * len(headers))} |"
            sections.append(
                DocumentSection(
                    index=0,
                    title="CSV Header",
                    content=content,
                    page_number=1,
                    character_count=len(content),
                    metadata={"format": "csv", "total_rows": 1, "columns": len(headers)},
                )
            )
        else:
            for sec_idx, i in enumerate(range(0, len(data_rows), rows_per_section)):
                chunk_rows = data_rows[i : i + rows_per_section]
                lines = []
                # Header
                lines.append("| " + " | ".join(headers) + " |")
                lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                # Rows
                for row in chunk_rows:
                    # Pad or truncate row to match headers
                    padded_row = row + [""] * (len(headers) - len(row))
                    lines.append("| " + " | ".join(padded_row[: len(headers)]) + " |")

                section_text = "\n".join(lines)
                start_row = i + 1
                end_row = min(i + rows_per_section, len(data_rows))
                sections.append(
                    DocumentSection(
                        index=sec_idx,
                        title=f"Rows {start_row}–{end_row}",
                        content=section_text,
                        page_number=1,
                        character_count=len(section_text),
                        metadata={
                            "format": "csv",
                            "start_row": start_row,
                            "end_row": end_row,
                            "columns": len(headers),
                        },
                    )
                )

        total_chars = sum(s.character_count for s in sections)

        return ParsedDocument(
            attachment_id=attachment_id,
            filename=filename,
            mime_type=mime_type or "text/csv",
            size=file_size,
            status="processed",
            total_characters=total_chars,
            page_count=1,
            section_count=len(sections),
            processed_at=self.get_current_timestamp(),
            sections=sections,
            metadata={
                "format": "csv",
                "total_rows": len(rows),
                "total_columns": len(headers),
                "delimiter": delimiter,
            },
        )
