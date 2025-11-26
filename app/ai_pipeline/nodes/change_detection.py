"""LangGraph node: change_detection

Compares old vs new regulation chunks and flags semantic changes.

Assumptions (temporary):
- One regulation_id + (old_version_id, new_version_id) per run. # TODO: allow batch
- Chunks are stored in regulation_chunks table via ChangeRepository. # TODO: confirm schema
- Pairing by section_idx. # TODO: confirm pairing key
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.ai_pipeline.prompts.change_detection_prompt import CHANGE_DETECTION_PROMPT
from app.ai_pipeline.state import AppState
from app.config.settings import settings
from app.core.database import AsyncSessionLocal
from app.core.repositories.change_repository import ChangeRepository


logger = logging.getLogger(__name__)


class ChangeDetectionNode:
    def __init__(
        self,
        llm_client,
        repository: Optional[ChangeRepository] = None,
        model_name: Optional[str] = None,
    ):
        self.llm = llm_client
        self.repository = repository or ChangeRepository()
        # TODO: confirm default model
        self.model_name = model_name or getattr(settings, "CHANGE_DETECTION_MODEL", "gpt-5-nano")

    async def run(self, state: AppState) -> AppState:
        change_context: Dict[str, Any] = state.get("change_context", {}) or {}

        regulation_id = change_context.get("regulation_id")
        new_version_id = change_context.get("new_version_id")
        old_version_id = change_context.get("old_version_id")

        # TODO: support batch regulations
        if regulation_id is None or new_version_id is None:
            state["change_detection"] = {
                "status": "error",
                "terminated": True,
                "error": "regulation_id/new_version_id missing",
            }
            return state

        async with AsyncSessionLocal() as session:
            pairs = await self.repository.fetch_pair_by_section(
                session, regulation_id, old_version_id, new_version_id
            )

        changes: List[Dict[str, Any]] = []
        for old_chunk, new_chunk in pairs:
            change_entry = await self._evaluate_pair(old_chunk, new_chunk, change_context)
            if change_entry:
                changes.append(change_entry)

        semantic_any = any(c.get("semantic_change") for c in changes)
        surface_any = any(c.get("surface_change") for c in changes)

        status = "changed" if semantic_any or surface_any else "no_change"
        terminated = not semantic_any  # terminate if no semantic change

        state["change_detection"] = {
            "status": status,
            "terminated": terminated,
            "changes": changes,
        }
        return state

    async def _evaluate_pair(
        self,
        old_chunk: Optional[Dict[str, Any]],
        new_chunk: Optional[Dict[str, Any]],
        change_context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        # Determine change_type
        if old_chunk and not new_chunk:
            change_type = "removed"
        elif new_chunk and not old_chunk:
            change_type = "added"
        elif old_chunk and new_chunk:
            change_type = "modified"
        else:
            return None

        old_text = (old_chunk or {}).get("content", {}).get("text") if old_chunk else None
        new_text = (new_chunk or {}).get("content", {}).get("text") if new_chunk else None

        # Minimal context: use provided spans if any
        indices = change_context.get("change_indices") or {}
        pair_key = self._make_pair_key(old_chunk, new_chunk)
        pair_indices = indices.get(pair_key) if isinstance(indices, dict) else None

        prompt = self._build_prompt(old_text, new_text, pair_indices, change_type)
        llm_out = await self._call_llm(prompt)

        return {
            "chunk_id": (new_chunk or old_chunk or {}).get("chunk_id"),
            "change_type": llm_out.get("change_type", change_type),
            "surface_change": llm_out.get("surface_change", False),
            "semantic_change": llm_out.get("semantic_change", False),
            "changed_sentences": llm_out.get("changed_sentences", []),
            "summary": llm_out.get("summary", ""),
            "reasons": llm_out.get("reasons", ""),
            "evidence_spans": llm_out.get("evidence_spans", []),
            "llm_confidence": llm_out.get("llm_confidence"),
            "indices": pair_indices,
        }

    def _make_pair_key(self, old_chunk: Optional[Dict[str, Any]], new_chunk: Optional[Dict[str, Any]]):
        # TODO: confirm key structure
        section_idx = None
        if old_chunk:
            section_idx = old_chunk.get("section_idx")
        if new_chunk and section_idx is None:
            section_idx = new_chunk.get("section_idx")
        return f"section_{section_idx}" if section_idx is not None else "unknown"

    def _build_prompt(
        self,
        old_text: Optional[str],
        new_text: Optional[str],
        indices: Optional[Any],
        change_type: str,
    ) -> str:
        payload = {
            "old_snippet": old_text or "",
            "new_snippet": new_text or "",
            "indices": indices,
            "change_type_hint": change_type,
        }
        return CHANGE_DETECTION_PROMPT + "\n" + json.dumps(payload, ensure_ascii=False)

    async def _call_llm(self, prompt: str) -> Dict[str, Any]:
        try:
            res = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            content = res.choices[0].message.content
            return json.loads(content)
        except Exception as exc:
            logger.warning("change_detection LLM failure: %s", exc)
            return {
                "surface_change": False,
                "semantic_change": False,
                "change_type": "modified",
                "changed_sentences": [],
                "summary": "",
                "reasons": "LLM error",
                "evidence_spans": [],
                "llm_confidence": None,
            }


_DEFAULT_CHANGE_NODE: Optional[ChangeDetectionNode] = None


def _get_default_llm_client():
    # Reuse mapping's pattern; lazily import to avoid dependency issues
    try:
        from openai import AsyncOpenAI
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("openai not installed") from exc
    return AsyncOpenAI()


def _get_default_change_node() -> ChangeDetectionNode:
    global _DEFAULT_CHANGE_NODE
    if _DEFAULT_CHANGE_NODE is None:
        _DEFAULT_CHANGE_NODE = ChangeDetectionNode(
            llm_client=_get_default_llm_client(),
        )
    return _DEFAULT_CHANGE_NODE


async def change_detection_node(state: AppState) -> AppState:
    node = _get_default_change_node()
    return await node.run(state)


__all__ = ["ChangeDetectionNode", "change_detection_node"]
