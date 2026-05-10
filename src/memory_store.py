"""ChromaDB vector store client for semantic memory embeddings."""

from __future__ import annotations

import uuid
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from src.config import get_settings

settings = get_settings()

COLLECTIONS = {
    "lessons": "aether_lessons",
    "trades": "aether_trade_outcomes",
    "observations": "aether_market_observations",
    "reasoning": "aether_reasoning_chains",
}


class MemoryStore:
    """ChromaDB-backed semantic memory for long-term pattern recall."""

    def __init__(self) -> None:
        self._client: Optional[chromadb.ClientAPI] = None
        self._collections: dict[str, chromadb.Collection] = {}

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is None:
            if settings.chroma_host:
                self._client = chromadb.HttpClient(
                    host=settings.chroma_host,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
            else:
                import os
                os.makedirs(settings.chroma_persist_dir, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=settings.chroma_persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
            logger.info(f"ChromaDB initialized at {settings.chroma_persist_dir}")
        return self._client

    def _get_collection(self, collection_key: str) -> chromadb.Collection:
        if collection_key not in self._collections:
            client = self._get_client()
            name = COLLECTIONS.get(collection_key, collection_key)
            self._collections[collection_key] = client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[collection_key]

    def add_memory(
        self,
        text: str,
        metadata: dict[str, Any],
        collection: str = "lessons",
        doc_id: Optional[str] = None,
    ) -> str:
        """Add a memory document to the vector store."""
        doc_id = doc_id or str(uuid.uuid4())
        coll = self._get_collection(collection)
        # Clean metadata — ChromaDB requires all values to be str/int/float/bool
        clean_meta = {
            k: str(v) if not isinstance(v, (str, int, float, bool)) else v
            for k, v in metadata.items()
        }
        try:
            coll.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[clean_meta],
            )
            logger.debug(f"Memory stored: {doc_id} in {collection}")
        except Exception as exc:
            logger.error(f"Failed to store memory {doc_id}: {exc}")
        return doc_id

    def search_memories(
        self,
        query: str,
        n_results: int = 3,
        collection: str = "lessons",
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Semantic search for relevant memories."""
        coll = self._get_collection(collection)
        try:
            kwargs: dict[str, Any] = {
                "query_texts": [query],
                "n_results": min(n_results, coll.count() or 1),
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            results = coll.query(**kwargs)

            memories: list[dict[str, Any]] = []
            if results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],  # type: ignore[index]
                    results["distances"][0],  # type: ignore[index]
                ):
                    memories.append({
                        "content": doc,
                        "metadata": meta or {},
                        "distance": float(dist),
                        "relevance": max(0.0, 1.0 - float(dist)),
                    })
            return memories
        except Exception as exc:
            logger.error(f"Memory search failed: {exc}")
            return []

    def delete_memory(self, doc_id: str, collection: str = "lessons") -> bool:
        """Delete a memory by ID."""
        coll = self._get_collection(collection)
        try:
            coll.delete(ids=[doc_id])
            return True
        except Exception as exc:
            logger.error(f"Failed to delete memory {doc_id}: {exc}")
            return False

    def count_memories(self, collection: str = "lessons") -> int:
        """Count documents in a collection."""
        try:
            coll = self._get_collection(collection)
            return coll.count()
        except Exception:
            return 0

    def add_lesson(self, title: str, content: str, metadata: dict[str, Any]) -> str:
        """Convenience method to store a lesson."""
        full_text = f"LESSON: {title}\n\n{content}"
        return self.add_memory(
            text=full_text,
            metadata={"title": title, "type": "lesson", **metadata},
            collection="lessons",
        )

    def add_trade_outcome(
        self,
        symbol: str,
        side: str,
        pnl_usd: float,
        reasoning: str,
        outcome_analysis: str,
    ) -> str:
        """Store a trade outcome for future recall."""
        outcome = "win" if pnl_usd > 0 else "loss"
        text = (
            f"TRADE OUTCOME: {outcome.upper()} on {symbol} ({side})\n"
            f"P&L: ${pnl_usd:+.2f}\n"
            f"Reasoning: {reasoning}\n"
            f"Analysis: {outcome_analysis}"
        )
        return self.add_memory(
            text=text,
            metadata={
                "symbol": symbol,
                "side": side,
                "pnl_usd": pnl_usd,
                "outcome": outcome,
                "type": "trade_outcome",
            },
            collection="trades",
        )

    def add_market_observation(
        self,
        symbol: str,
        observation: str,
        indicators: dict[str, Any],
    ) -> str:
        """Store a market observation for pattern recall."""
        text = f"MARKET OBSERVATION: {symbol}\n{observation}"
        meta = {"symbol": symbol, "type": "observation"}
        meta.update({k: str(v) for k, v in indicators.items()})
        return self.add_memory(text=text, metadata=meta, collection="observations")

    def search_relevant_past(self, current_context: str, n: int = 3) -> list[dict[str, Any]]:
        """Multi-collection semantic search for the most relevant past experiences."""
        all_results: list[dict[str, Any]] = []
        for coll_key in ["lessons", "trades", "observations"]:
            results = self.search_memories(current_context, n_results=2, collection=coll_key)
            for r in results:
                r["collection"] = coll_key
                all_results.append(r)
        # Sort by relevance (lower distance = more relevant)
        all_results.sort(key=lambda x: x["distance"])
        return all_results[:n]


_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
