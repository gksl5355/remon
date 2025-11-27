"""
Temporary repository for regulation chunk comparison. # TODO: replace with final schema/table.
Assumes a regulation_chunks table with JSONB content.
"""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ChangeRepository:
    """Load old/new chunks for change detection. # TODO: confirm schema/columns.

    Assumed schema (temporary):
    - table: regulation_chunks  # TODO
    - columns: chunk_id, regulation_id, version_id, section_idx, content_jsonb, ingested_at
    - content_jsonb is assumed to have a "text" field. # TODO
    """

    async def fetch_chunks(
        self,
        db: AsyncSession,
        regulation_id: Any,
        version_id: Any,
    ) -> List[Dict[str, Any]]:
        """Fetch all chunks for a regulation/version. # TODO: optimize/index
        Returns rows with chunk_id, section_idx, content_jsonb.
        """

        query = text(
            """
            SELECT chunk_id, regulation_id, version_id, section_idx, content_jsonb, ingested_at
            FROM regulation_chunks  -- TODO: table name
            WHERE regulation_id = :regulation_id AND version_id = :version_id
            ORDER BY section_idx, chunk_id
            """
        )
        result = await db.execute(
            query,
            {"regulation_id": regulation_id, "version_id": version_id},
        )
        return [dict(r) for r in result.mappings().all()]

    async def fetch_pair_by_section(
        self,
        db: AsyncSession,
        regulation_id: Any,
        old_version_id: Any,
        new_version_id: Any,
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Fetch old/new chunks matched by section_idx. # TODO: confirm pairing key.

        Returns list of (old_chunk, new_chunk). Missing counterpart will be None.
        """

        # TODO: refine pairing (e.g., chunk_id/hash). This is a simple section_idx join.
        query = text(
            """
            WITH old_chunks AS (
                SELECT section_idx, chunk_id, content_jsonb, ingested_at
                FROM regulation_chunks
                WHERE regulation_id = :reg_id AND version_id = :old_vid
            ),
            new_chunks AS (
                SELECT section_idx, chunk_id, content_jsonb, ingested_at
                FROM regulation_chunks
                WHERE regulation_id = :reg_id AND version_id = :new_vid
            )
            SELECT
                o.section_idx AS section_idx,
                o.chunk_id    AS old_chunk_id,
                o.content_jsonb AS old_content,
                n.chunk_id    AS new_chunk_id,
                n.content_jsonb AS new_content
            FROM old_chunks o
            FULL OUTER JOIN new_chunks n USING (section_idx)
            ORDER BY section_idx
            """
        )
        params = {
            "reg_id": regulation_id,
            "old_vid": old_version_id,
            "new_vid": new_version_id,
        }
        result = await db.execute(query, params)
        rows = result.mappings().all()
        pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for r in rows:
            old_chunk = None
            new_chunk = None
            if r.get("old_chunk_id"):
                old_chunk = {
                    "chunk_id": r["old_chunk_id"],
                    "section_idx": r["section_idx"],
                    "content": r["old_content"],
                }
            if r.get("new_chunk_id"):
                new_chunk = {
                    "chunk_id": r["new_chunk_id"],
                    "section_idx": r["section_idx"],
                    "content": r["new_content"],
                }
            pairs.append((old_chunk, new_chunk))
        return pairs


__all__ = ["ChangeRepository"]
