"""Tests for MemoryPipeline."""
import numpy as np
import pytest

from brain.store import MemoryStore
from brain.pipeline import MemoryPipeline


@pytest.fixture
def store(tmp_path):
    """Fresh MemoryStore backed by a temp SQLite file."""
    return MemoryStore(db_path=str(tmp_path / "test_pipeline.db"))


@pytest.fixture
def pipeline(store):
    """MemoryPipeline wrapping the fixture store."""
    return MemoryPipeline(store=store, embedding_dim=128)


# ------------------------------------------------------------------
# Embedding
# ------------------------------------------------------------------


def test_embed_text_deterministic(pipeline):
    """Same text → same embedding vector."""
    text = "The dragon guards the treasure"
    emb1 = pipeline.embed_text(text)
    emb2 = pipeline.embed_text(text)
    np.testing.assert_array_equal(emb1, emb2)


def test_embed_text_different(pipeline):
    """Different text → different embedding vectors."""
    emb1 = pipeline.embed_text("fire")
    emb2 = pipeline.embed_text("ice")
    assert not np.allclose(emb1, emb2)


def test_embed_text_shape(pipeline):
    """Embedding has the configured dimension."""
    emb = pipeline.embed_text("test")
    assert emb.shape == (pipeline.embedding_dim,)
    # Normalised
    assert np.isclose(np.linalg.norm(emb), 1.0)


# ------------------------------------------------------------------
# process_event
# ------------------------------------------------------------------


def test_process_event_stores_memory(pipeline, store):
    """An event dict results in a memory stored in the backend."""
    event = {
        "content": "The party entered the dungeon",
        "layer": "working",
        "tags": {"location": "dungeon"},
        "metadata": {"source": "narrator"},
        "player_id": "p1",
    }
    mid = pipeline.process_event(event)
    assert isinstance(mid, int)
    assert mid > 0

    mem = store.get_memory(mid)
    assert mem is not None
    assert mem["content"] == "The party entered the dungeon"
    assert mem["layer"] == "working"
    assert mem["tags"] == {"location": "dungeon"}
    assert mem["player_id"] == "p1"
    assert mem["embedding"] is not None


def test_process_event_defaults(pipeline, store):
    """Event without layer/tags/metadata/player_id uses defaults."""
    mid = pipeline.process_event({"content": "Minimal event"})
    mem = store.get_memory(mid)
    assert mem["layer"] == "working"
    assert mem["tags"] == {}
    assert mem["metadata"] == {}
    assert mem["player_id"] == "default"


# ------------------------------------------------------------------
# retrieve_context
# ------------------------------------------------------------------


def test_retrieve_context(pipeline, store):
    """Storing several memories then querying returns relevant results."""
    store.add_memory("Fire spell deals 1d6 damage", layer="working",
                     embedding=pipeline.embed_text("Fire spell deals 1d6 damage"),
                     player_id="p1")
    store.add_memory("The shopkeeper sells potions", layer="short_term",
                     embedding=pipeline.embed_text("The shopkeeper sells potions"),
                     player_id="p1")
    store.add_memory("Lightning bolt hits 3 targets", layer="long_term",
                     embedding=pipeline.embed_text("Lightning bolt hits 3 targets"),
                     player_id="p1")

    results = pipeline.retrieve_context("fire spell", player_id="p1", top_k=2)
    assert len(results) <= 2
    # The fire-related memory should rank highest (or close to it)
    contents = [r["content"] for r in results]
    assert any("Fire" in c for c in contents)


# ------------------------------------------------------------------
# store_with_embedding
# ------------------------------------------------------------------


def test_store_with_embedding(pipeline, store):
    """Convenience method embeds and stores in one step."""
    mid = pipeline.store_with_embedding(
        content="Dark cave ahead",
        layer="working",
        tags={"hazard": True},
        player_id="p2",
    )
    mem = store.get_memory(mid)
    assert mem["content"] == "Dark cave ahead"
    assert mem["layer"] == "working"
    assert mem["tags"] == {"hazard": True}
    assert mem["player_id"] == "p2"
    assert mem["embedding"] is not None
    assert mem["embedding"].shape == (128,)
