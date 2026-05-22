"""MemoryPipeline: Event → embed → store → retrieve flow for Echo Brain."""
import hashlib
import numpy as np
from brain.store import MemoryStore


class MemoryPipeline:
    def __init__(self, store: MemoryStore, embedding_dim: int = 128):
        self.store = store
        self.embedding_dim = embedding_dim

    def embed_text(self, text: str) -> np.ndarray:
        """Create a deterministic embedding from text.
        MVP: hash-based random vector (consistent for same text).
        Returns numpy array of shape (embedding_dim,)."""
        h = hashlib.sha256(text.encode("utf-8")).digest()
        rng = np.random.RandomState(int(np.frombuffer(h, dtype=np.uint32).sum()) % (2**32))
        vec = rng.randn(self.embedding_dim).astype(np.float64)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    def process_event(self, event: dict) -> int:
        """Process a raw event into a stored memory.
        Event: {content: str, layer: str, tags: dict, metadata: dict, player_id: str}
        Embeds content, stores in brain. Returns memory ID."""
        content = event["content"]
        layer = event.get("layer", "working")
        tags = event.get("tags", {})
        metadata = event.get("metadata", {})
        player_id = event.get("player_id", "default")

        embedding = self.embed_text(content)
        return self.store.add_memory(
            content=content,
            layer=layer,
            tags=tags,
            metadata=metadata,
            embedding=embedding,
            player_id=player_id,
        )

    def retrieve_context(
        self, query: str, player_id: str = "default", top_k: int = 5
    ) -> list:
        """Retrieve relevant memories for a query.
        Embeds query, searches all layers, returns combined results."""
        query_emb = self.embed_text(query)
        return self.store.search_similar(
            query_embedding=query_emb, top_k=top_k, player_id=player_id
        )

    def store_with_embedding(
        self,
        content: str,
        layer: str,
        tags: dict = None,
        metadata: dict = None,
        player_id: str = "default",
    ) -> int:
        """Convenience: embed content and store in one step."""
        embedding = self.embed_text(content)
        return self.store.add_memory(
            content=content,
            layer=layer,
            tags=tags,
            metadata=metadata,
            embedding=embedding,
            player_id=player_id,
        )
