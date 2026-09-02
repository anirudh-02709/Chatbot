from typing import Optional
from app.services.parsers.base import BaseDocumentParser
from app.services.parsers.txt_parser import TxtParser
from app.services.parsers.markdown_parser import MarkdownParser
from app.services.parsers.json_parser import JsonParser
from app.services.parsers.csv_parser import CsvParser
from app.services.parsers.pdf_parser import PdfParser
from app.services.parsers.docx_parser import DocxParser


class DocumentParserRegistry:
    """Registry and dispatcher for format-specific document parsers."""

    def __init__(self):
        self._parsers: dict[str, BaseDocumentParser] = {
            ".txt": TxtParser(),
            ".md": MarkdownParser(),
            ".json": JsonParser(),
            ".csv": CsvParser(),
            ".pdf": PdfParser(),
            ".docx": DocxParser(),
        }
        self._mime_map: dict[str, BaseDocumentParser] = {
            "text/plain": self._parsers[".txt"],
            "text/markdown": self._parsers[".md"],
            "text/x-markdown": self._parsers[".md"],
            "application/json": self._parsers[".json"],
            "text/csv": self._parsers[".csv"],
            "application/csv": self._parsers[".csv"],
            "application/pdf": self._parsers[".pdf"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": self._parsers[".docx"],
        }

    def get_parser(
        self,
        extension: str,
        mime_type: Optional[str] = None,
    ) -> Optional[BaseDocumentParser]:
        """Lookup parser by extension first, then by MIME type."""
        ext_clean = extension.lower() if extension else ""
        if ext_clean in self._parsers:
            return self._parsers[ext_clean]

        if mime_type:
            clean_mime = mime_type.lower().split(";")[0].strip()
            if clean_mime in self._mime_map:
                return self._mime_map[clean_mime]

        return None


# Global singleton parser registry
parser_registry = DocumentParserRegistry()
