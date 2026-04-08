"""API routes for knowledge graph management."""

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from swarm import store
from swarm.knowledge.extractor import extract_from_text

router = APIRouter()

PARALLEL_BATCH_SIZE = 10  # Process up to 10 articles at once


class IngestRequest(BaseModel):
    articles: list[str]  # List of news article texts


class IngestSingleRequest(BaseModel):
    text: str
    label: str = ""  # Optional source label


@router.get("/")
async def get_graph():
    """Return the full knowledge graph."""
    return store.graph.to_dict()


@router.get("/stats")
async def graph_stats():
    """Return graph statistics."""
    return store.graph.stats()


@router.get("/context/{executive_name}")
async def get_executive_context(executive_name: str):
    """Get all knowledge graph context for a specific executive."""
    return store.graph.get_context_for_executive(executive_name)


async def _extract_one(article: str, index: int) -> dict:
    """Extract entities from one article, returning result dict."""
    label = f"article_{index+1}"
    try:
        extracted = await extract_from_text(article)
        entities_added = 0
        rels_added = 0
        for entity in extracted.get("entities", []):
            store.graph.add_entity(entity, source_label=label)
            entities_added += 1
        for rel in extracted.get("relationships", []):
            store.graph.add_relationship(rel, source_label=label)
            rels_added += 1
        return {"article": index + 1, "entities": entities_added, "relationships": rels_added, "status": "ok"}
    except Exception as e:
        return {"article": index + 1, "status": "error", "error": str(e)}


@router.post("/ingest")
async def ingest_articles(req: IngestRequest):
    """Ingest news articles into the knowledge graph IN PARALLEL.

    Processes up to 10 articles concurrently via asyncio.gather.
    """
    results = []

    # Process in parallel batches
    for batch_start in range(0, len(req.articles), PARALLEL_BATCH_SIZE):
        batch = req.articles[batch_start:batch_start + PARALLEL_BATCH_SIZE]
        tasks = [_extract_one(article, batch_start + i) for i, article in enumerate(batch)]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)

    # Update knowledge store for all profiled executives
    for name in store.profiles:
        context = store.graph.get_context_for_executive(name)
        if any(context.values()):
            store.knowledge[name] = context

    return {
        "articles_processed": len(req.articles),
        "results": results,
        "graph_stats": store.graph.stats(),
    }


@router.post("/ingest-single")
async def ingest_single(req: IngestSingleRequest):
    """Ingest a single news article into the knowledge graph."""
    extracted = await extract_from_text(req.text)
    label = req.label or "manual"

    for entity in extracted.get("entities", []):
        store.graph.add_entity(entity, source_label=label)
    for rel in extracted.get("relationships", []):
        store.graph.add_relationship(rel, source_label=label)

    # Update knowledge for profiled executives
    for name in store.profiles:
        context = store.graph.get_context_for_executive(name)
        if any(context.values()):
            store.knowledge[name] = context

    return {
        "extracted": extracted,
        "graph_stats": store.graph.stats(),
    }
