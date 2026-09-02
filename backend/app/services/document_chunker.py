import logging
from typing import Optional
from app.config import Settings, get_settings
from app.models.document import (
    ParsedDocument,
    DocumentSection,
    DocumentChunk,
    DocumentChunksResponse,
)

logger = logging.getLogger("chatbot.document_chunker")


class DocumentChunker:
    """Service to transform a ParsedDocument into retrieval-ready DocumentChunks."""

    # Natural boundary separator hierarchy
    SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def _split_text(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        separators: list[str],
    ) -> list[str]:
        """
        Recursively splits text using natural separators into pieces under chunk_size with overlap.
        """
        final_chunks: list[str] = []
        clean_text = text.strip()
        if not clean_text:
            return final_chunks

        if len(clean_text) <= chunk_size:
            return [clean_text]

        # Find best separator that exists in text
        separator = ""
        new_separators: list[str] = []
        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in clean_text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        # Split on chosen separator
        if separator != "":
            splits = clean_text.split(separator)
        else:
            # Fallback: slice into chunk_size pieces
            return [
                clean_text[i : i + chunk_size].strip()
                for i in range(0, len(clean_text), max(1, chunk_size - chunk_overlap))
                if clean_text[i : i + chunk_size].strip()
            ]

        # Handle any splits that individually exceed chunk_size
        good_splits: list[str] = []
        for s in splits:
            s_clean = s.strip()
            if not s_clean:
                continue
            if len(s_clean) > chunk_size and new_separators:
                sub_chunks = self._split_text(s_clean, chunk_size, chunk_overlap, new_separators)
                good_splits.extend(sub_chunks)
            else:
                good_splits.append(s_clean)

        if not good_splits:
            return [clean_text]

        # Accumulate splits into chunks with overlap
        current_pieces: list[str] = []
        current_len = 0

        for piece in good_splits:
            piece_len = len(piece)
            sep_len = len(separator) if current_pieces else 0

            if current_len + sep_len + piece_len <= chunk_size:
                current_pieces.append(piece)
                current_len += sep_len + piece_len
            else:
                if current_pieces:
                    chunk_text = separator.join(current_pieces).strip()
                    if chunk_text:
                        final_chunks.append(chunk_text)

                    # Build overlap from the end of current_pieces
                    overlap_pieces: list[str] = []
                    overlap_len = 0
                    for prev_piece in reversed(current_pieces):
                        p_sep = len(separator) if overlap_pieces else 0
                        if overlap_len + p_sep + len(prev_piece) <= chunk_overlap:
                            overlap_pieces.insert(0, prev_piece)
                            overlap_len += p_sep + len(prev_piece)
                        else:
                            break

                    current_pieces = overlap_pieces
                    current_len = len(separator.join(current_pieces)) if current_pieces else 0

                current_pieces.append(piece)
                current_len += (len(separator) if len(current_pieces) > 1 else 0) + piece_len

        if current_pieces:
            chunk_text = separator.join(current_pieces).strip()
            if chunk_text and (not final_chunks or chunk_text != final_chunks[-1]):
                final_chunks.append(chunk_text)

        return final_chunks

    def chunk_section(
        self,
        section: DocumentSection,
        attachment_id: str,
        chunk_size: int,
        chunk_overlap: int,
        global_chunk_start_idx: int = 0,
    ) -> list[DocumentChunk]:
        """
        Chunks an individual DocumentSection, preserving page number, title, and metadata.
        """
        raw_content = section.content.strip()
        if not raw_content:
            return []

        text_chunks = self._split_text(
            raw_content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.SEPARATORS,
        )

        chunks: list[DocumentChunk] = []
        for i, text in enumerate(text_chunks):
            chunk_idx = global_chunk_start_idx + i
            chunk_id = f"chk_{attachment_id}_s{section.index}_c{i}"
            
            chunk_metadata = {
                **section.metadata,
                "section_index": section.index,
                "chunk_in_section": i,
                "total_chunks_in_section": len(text_chunks),
            }

            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    attachment_id=attachment_id,
                    document_section_index=section.index,
                    chunk_index=chunk_idx,
                    content=text,
                    character_count=len(text),
                    page_number=section.page_number,
                    section_title=section.title,
                    metadata=chunk_metadata,
                )
            )

        return chunks

    def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> DocumentChunksResponse:
        """
        Transforms a ParsedDocument into a structured list of DocumentChunks.
        """
        effective_chunk_size = chunk_size or self.settings.default_chunk_size
        effective_overlap = (
            chunk_overlap
            if chunk_overlap is not None
            else self.settings.default_chunk_overlap
        )

        # Enforce bounds
        effective_chunk_size = max(self.settings.min_chunk_size, effective_chunk_size)
        effective_overlap = min(effective_overlap, effective_chunk_size // 2)

        all_chunks: list[DocumentChunk] = []
        global_idx = 0

        for section in parsed_doc.sections:
            section_chunks = self.chunk_section(
                section=section,
                attachment_id=parsed_doc.attachment_id,
                chunk_size=effective_chunk_size,
                chunk_overlap=effective_overlap,
                global_chunk_start_idx=global_idx,
            )
            all_chunks.extend(section_chunks)
            global_idx += len(section_chunks)

        total_chars = sum(c.character_count for c in all_chunks)
        logger.info(
            f"Chunked document {parsed_doc.attachment_id} ({parsed_doc.filename}) into {len(all_chunks)} chunks ({total_chars} total characters)"
        )

        return DocumentChunksResponse(
            attachment_id=parsed_doc.attachment_id,
            filename=parsed_doc.filename,
            total_chunks=len(all_chunks),
            total_characters=total_chars,
            chunk_size=effective_chunk_size,
            chunk_overlap=effective_overlap,
            chunks=all_chunks,
        )


# Global singleton chunker instance
document_chunker = DocumentChunker()
