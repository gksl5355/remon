"""
module: embedding_chain.py
description: Converts refined regulation clauses into embeddings and loads them
into the Chroma vector store without invoking any LLM components.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Sequence, TypedDict

from sentence_transformers import SentenceTransformer

from app.vectorstore.vector_client import VectorClient

logger = logging.getLogger(__name__)


class RefinedClause(TypedDict, total=False):
    """
    Schema for a single clause emitted by the Refine pipeline.
    """

    clause_id: str | int
    text: str
    country: str | None
    lang: str | None
    source: str | None
    effective_date: str | None
    title: str | None


class RefineOutput(TypedDict, total=False):
    """
    Minimal schema the embedding chain expects from Refine.
    """

    regulation_id: str | int | None
    regulation_title: str | None
    document_id: str | None
    source: str | None
    country: str | None
    lang: str | None
    clauses: list[RefinedClause]


@dataclass(slots=True)
class EmbeddingRunResult:
    """
    Structured return value for easier logging and downstream tracking.
    """

    regulation_id: str | int | None
    inserted_count: int
    embedding_time_sec: float
    insert_time_sec: float
    skipped_clause_ids: list[str]


class EmbeddingChain:
    """
    Handles the text -> embedding -> vector insert flow for refined clauses.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        batch_size: int = 16,
        normalize_embeddings: bool = True,
        vector_client: VectorClient | None = None,
        model: SentenceTransformer | None = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.vector_client = vector_client or VectorClient()
        self.model = model or SentenceTransformer(model_name)

    def run(self, refine_output: RefineOutput) -> EmbeddingRunResult:
        """
        Public entry point: embeds and stores clauses from Refine output.
        """

        texts, metadatas, skipped = self._prepare_payload(refine_output)
        regulation_id = refine_output.get("regulation_id")
        if not texts:
            logger.warning(
                "No valid clauses to embed for regulation_id=%s", regulation_id
            )
            return EmbeddingRunResult(
                regulation_id=regulation_id,
                inserted_count=0,
                embedding_time_sec=0.0,
                insert_time_sec=0.0,
                skipped_clause_ids=skipped,
            )

        embed_start = time.perf_counter()
        embeddings = self._embed(texts)
        embed_time = time.perf_counter() - embed_start

        insert_start = time.perf_counter()
        self.vector_client.insert(texts=texts, embeddings=embeddings, metadatas=metadatas)
        insert_time = time.perf_counter() - insert_start

        logger.info(
            "Embedded %s clauses for regulation_id=%s in %.3fs (insert %.3fs)",
            len(texts),
            regulation_id,
            embed_time,
            insert_time,
        )

        return EmbeddingRunResult(
            regulation_id=regulation_id,
            inserted_count=len(texts),
            embedding_time_sec=embed_time,
            insert_time_sec=insert_time,
            skipped_clause_ids=skipped,
        )

    def _prepare_payload(
        self, refine_output: RefineOutput
    ) -> tuple[list[str], list[dict[str, Any]], list[str]]:
        """
        Builds the documents and metadata list expected by the vector client.
        """

        clauses = refine_output.get("clauses") or []
        texts: list[str] = []
        metadatas: list[dict[str, Any]] = []
        skipped_ids: list[str] = []

        for clause in clauses:
            text = clause.get("text")
            clause_id = clause.get("clause_id")

            if not text or clause_id is None:
                skipped_ids.append(str(clause_id) if clause_id is not None else "missing")
                logger.warning(
                    "Skipping clause without text/id (clause_id=%s, regulation_id=%s)",
                    clause_id,
                    refine_output.get("regulation_id"),
                )
                continue

            texts.append(text)
            metadatas.append(
                {
                    "regulation_id": refine_output.get("regulation_id"),
                    "regulation_title": refine_output.get("regulation_title"),
                    "document_id": refine_output.get("document_id"),
                    "clause_id": clause_id,
                    "country": clause.get("country") or refine_output.get("country"),
                    "lang": clause.get("lang") or refine_output.get("lang"),
                    "source": clause.get("source") or refine_output.get("source"),
                    "effective_date": clause.get("effective_date"),
                    "title": clause.get("title"),
                }
            )

        return texts, metadatas, skipped_ids

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Generates embeddings for the provided texts using the configured model.
        """

        embeddings = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )
        return embeddings.tolist()


def embed_refined_document(
    refine_output: RefineOutput,
    *,
    model_name: str = "BAAI/bge-m3",
    batch_size: int = 16,
) -> EmbeddingRunResult:
    """
    Convenience function for quick one-off executions outside of the class.
    """

    chain = EmbeddingChain(model_name=model_name, batch_size=batch_size)
    return chain.run(refine_output)
