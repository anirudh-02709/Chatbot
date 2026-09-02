import array
import json
import logging
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import Settings, get_settings
from app.models.retrieval import StoredVector, RetrievalResult

logger = logging.getLogger("chatbot.vector_store")


class LocalVectorStore:
    """Persistent SQLite-backed local vector store for document chunk embeddings."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        backend_root = Path(__file__).resolve().parent.parent.parent
        self.store_dir = (backend_root / self.settings.vector_store_dir).resolve()
        self.db_path = self.store_dir / "vectors.db"
        self._ensure_storage()
        self._init_db()

    def _ensure_storage(self) -> None:
        """Ensure storage directory exists."""
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Create a SQLite connection with row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    chunk_id TEXT PRIMARY KEY,
                    attachment_id TEXT NOT NULL,
                    document_section_index INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    vector_norm REAL NOT NULL,
                    character_count INTEGER NOT NULL,
                    page_number INTEGER,
                    section_title TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vectors_attachment ON vectors(attachment_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vectors_chunk ON vectors(chunk_id);")
            conn.commit()

    @staticmethod
    def _pack_vector(vector: list[float]) -> bytes:
        """Packs float list into high-efficiency float32 binary buffer."""
        arr = array.array("f", vector)
        return arr.tobytes()

    @staticmethod
    def _unpack_vector(blob: bytes) -> array.array:
        """Unpacks float32 binary buffer into array of floats."""
        arr = array.array("f")
        arr.frombytes(blob)
        return arr

    def replace_attachment(
        self,
        attachment_id: str,
        stored_vectors: list[StoredVector],
    ) -> int:
        """
        Atomically replaces all stored vector chunks for an attachment inside a transaction.
        """
        expected_dim = self.settings.embedding_dimensions
        now_ts = datetime.now(timezone.utc).isoformat()

        # Validate vectors
        for sv in stored_vectors:
            if len(sv.embedding) != expected_dim:
                raise ValueError(
                    f"Vector dimension mismatch for chunk {sv.chunk_id}: expected {expected_dim}, got {len(sv.embedding)}"
                )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Atomic deletion of previous index for this attachment
            cursor.execute("DELETE FROM vectors WHERE attachment_id = ?", (attachment_id,))

            # Batch insert new vectors
            rows_to_insert = []
            for sv in stored_vectors:
                norm = math.sqrt(sum(x * x for x in sv.embedding))
                blob = self._pack_vector(sv.embedding)
                meta_json = json.dumps(sv.metadata, ensure_ascii=False)

                rows_to_insert.append((
                    sv.chunk_id,
                    sv.attachment_id,
                    sv.document_section_index,
                    sv.chunk_index,
                    sv.content,
                    blob,
                    norm,
                    sv.character_count,
                    sv.page_number,
                    sv.section_title,
                    meta_json,
                    now_ts,
                ))

            if rows_to_insert:
                cursor.executemany(
                    """
                    INSERT INTO vectors (
                        chunk_id, attachment_id, document_section_index, chunk_index,
                        content, embedding, vector_norm, character_count,
                        page_number, section_title, metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows_to_insert,
                )

            conn.commit()
            logger.info(f"Indexed {len(rows_to_insert)} vector chunks for attachment {attachment_id}")
            return len(rows_to_insert)

    def delete_attachment(self, attachment_id: str) -> int:
        """Deletes all indexed vectors for an attachment."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vectors WHERE attachment_id = ?", (attachment_id,))
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Deleted {deleted} vector chunks for attachment {attachment_id}")
            return deleted

    def get_attachment_stats(self, attachment_id: str) -> dict:
        """Returns indexing statistics for an attachment."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*), MIN(created_at) FROM vectors WHERE attachment_id = ?",
                (attachment_id,),
            )
            row = cursor.fetchone()
            count = row[0] if row else 0
            created_at = row[1] if row and row[1] else None
            return {
                "attachment_id": attachment_id,
                "chunk_count": count,
                "created_at": created_at,
            }

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_score: float = 0.0,
        attachment_id: Optional[str] = None,
        attachment_ids: Optional[list[str]] = None,
    ) -> list[RetrievalResult]:
        """
        Calculates cosine similarity between query_vector and stored chunks,
        returning top_k results sorted by descending similarity score.
        Supports single or multiple attachment_id filters.
        """
        expected_dim = self.settings.embedding_dimensions
        if len(query_vector) != expected_dim:
            raise ValueError(
                f"Query vector dimension mismatch: expected {expected_dim}, got {len(query_vector)}"
            )

        query_norm = math.sqrt(sum(q * q for q in query_vector))
        if query_norm == 0.0:
            return []

        # Normalize attachment filters
        effective_ids: list[str] = []
        if attachment_ids:
            effective_ids = [aid for aid in attachment_ids if aid]
        elif attachment_id:
            effective_ids = [attachment_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            if effective_ids:
                placeholders = ",".join("?" for _ in effective_ids)
                cursor.execute(
                    f"""
                    SELECT chunk_id, attachment_id, document_section_index, chunk_index,
                           content, embedding, vector_norm, character_count,
                           page_number, section_title, metadata
                    FROM vectors
                    WHERE attachment_id IN ({placeholders})
                    """,
                    effective_ids,
                )
            else:
                cursor.execute(
                    """
                    SELECT chunk_id, attachment_id, document_section_index, chunk_index,
                           content, embedding, vector_norm, character_count,
                           page_number, section_title, metadata
                    FROM vectors
                    """
                )

            rows = cursor.fetchall()

        candidates: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            doc_norm = row["vector_norm"]
            if doc_norm == 0.0:
                continue

            # Unpack float32 buffer
            doc_vec = self._unpack_vector(row["embedding"])
            # Fast dot product
            dot = sum(q * d for q, d in zip(query_vector, doc_vec))
            sim = dot / (query_norm * doc_norm)

            if sim >= min_score:
                candidates.append((sim, row))

        # Sort by similarity descending, then section index, chunk index
        candidates.sort(
            key=lambda item: (
                -item[0],
                item[1]["document_section_index"],
                item[1]["chunk_index"],
            )
        )

        results: list[RetrievalResult] = []
        for sim, row in candidates[:top_k]:
            try:
                meta = json.loads(row["metadata"]) if row["metadata"] else {}
            except Exception:
                meta = {}

            results.append(
                RetrievalResult(
                    chunk_id=row["chunk_id"],
                    attachment_id=row["attachment_id"],
                    content=row["content"],
                    similarity_score=round(sim, 6),
                    document_section_index=row["document_section_index"],
                    chunk_index=row["chunk_index"],
                    page_number=row["page_number"],
                    section_title=row["section_title"],
                    metadata=meta,
                )
            )

        return results


# Global singleton instance
local_vector_store = LocalVectorStore()
