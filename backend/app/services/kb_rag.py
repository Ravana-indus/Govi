"""Knowledge base ingestion + retrieval (RAG).

Ingestion: doc -> clean -> chunk (~500 tokens, overlap) -> embed -> store.
Retrieval: top-k by vector similarity, filtered by crop_id / topic / language.

On Postgres this uses pgvector + an ivfflat index. In the keyless dev run the
embeddings are JSON and similarity is computed in Python over the (small)
candidate set — correct, just not indexed. Full ingestion/admin authoring is
Phase 2; this provides the retrieval seam the Crop Doctor cites against.
"""
from __future__ import annotations

import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeChunk, KnowledgeDoc
from app.gateway import get_gateway

_CHUNK_WORDS = 120        # ~500 tokens
_OVERLAP_WORDS = 20


def _chunk(text: str) -> list[str]:
    words = re.sub(r"\s+", " ", text).strip().split(" ")
    if not words or words == [""]:
        return []
    chunks, i = [], 0
    step = max(1, _CHUNK_WORDS - _OVERLAP_WORDS)
    while i < len(words):
        chunks.append(" ".join(words[i:i + _CHUNK_WORDS]))
        i += step
    return chunks


def ingest(db: Session, doc: KnowledgeDoc) -> int:
    """(Re)index a doc's chunks. Returns chunk count."""
    db.query(KnowledgeChunk).filter(KnowledgeChunk.doc_id == doc.id).delete()
    gw = get_gateway()
    n = 0
    for ordinal, chunk_text in enumerate(_chunk(doc.body)):
        db.add(KnowledgeChunk(
            doc_id=doc.id, chunk_text=chunk_text,
            embedding=gw.embed(chunk_text), ordinal=ordinal,
        ))
        n += 1
    db.flush()
    return n


def ingest_text(db: Session, *, title: str, body: str, crop_id: str | None,
                topic: str, language: str = "en", source: str | None = None,
                validated_by: str | None = None, status: str = "validated") -> KnowledgeDoc:
    """Create a KnowledgeDoc and index it in one call (used by seed + admin import)."""
    doc = KnowledgeDoc(title=title, body=body, crop_id=crop_id, topic=topic,
                       language=language, source=source, validated_by=validated_by,
                       version=1, status=status)
    db.add(doc)
    db.flush()
    if status == "validated":
        ingest(db, doc)
    return doc


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve(db: Session, query: str, *, crop_id: str | None = None,
             topic: str | None = None, language: str | None = None,
             k: int = 3) -> list[tuple[KnowledgeChunk, float]]:
    gw = get_gateway()
    qvec = gw.embed(query)

    stmt = select(KnowledgeChunk).join(KnowledgeDoc)
    if crop_id:
        stmt = stmt.where(KnowledgeDoc.crop_id == crop_id)
    if topic:
        stmt = stmt.where(KnowledgeDoc.topic == topic)
    if language:
        stmt = stmt.where(KnowledgeDoc.language == language)
    stmt = stmt.where(KnowledgeDoc.status == "validated")

    candidates = list(db.scalars(stmt))
    scored = [(c, _cosine(qvec, c.embedding or [])) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def find_treatment_doc(db: Session, *, label: str, crop_id: str | None,
                       language: str) -> KnowledgeDoc | None:
    """Find a validated treatment doc for a disease label (RAG-scoped)."""
    hits = retrieve(db, query=label.replace("_", " "), crop_id=crop_id,
                    topic="disease", k=1)
    if hits:
        return db.get(KnowledgeDoc, hits[0][0].doc_id)
    # Fallback: any validated disease doc mentioning the label.
    stmt = (
        select(KnowledgeDoc)
        .where(KnowledgeDoc.topic == "disease", KnowledgeDoc.status == "validated")
        .where(KnowledgeDoc.body.ilike(f"%{label.replace('_', ' ')}%"))
    )
    return db.scalar(stmt)


def cited_treatment(db: Session, *, label: str, symptom_text: str | None,
                    crop_id: str | None, language: str, k: int = 3):
    """Return (best_doc, citations) for a disease label + optional symptom text.

    Citations let the Crop Doctor make every answer traceable to a validated
    KnowledgeDoc (doc_id + title + source)."""
    label_text = label.replace("_", " ")
    citations: list[dict] = []

    # 1) Exact label match in a validated disease doc — the most reliable signal,
    #    and correct even when embeddings are the deterministic mock. Preference:
    #    farmer-language + crop, then language, then crop, then any (English
    #    fallback) — satisfies the content-i18n requirement.
    def _exact(crop_scoped: bool, lang_scoped: bool):
        stmt = (select(KnowledgeDoc)
                .where(KnowledgeDoc.topic == "disease",
                       KnowledgeDoc.status == "validated",
                       KnowledgeDoc.body.ilike(f"%{label_text}%")))
        if crop_scoped and crop_id:
            stmt = stmt.where(KnowledgeDoc.crop_id == crop_id)
        if lang_scoped:
            stmt = stmt.where(KnowledgeDoc.language == language)
        return db.scalar(stmt)

    best = None
    for cs, ls in ((True, True), (False, True), (True, False), (False, False)):
        best = _exact(cs, ls)
        if best:
            break
    if best:
        citations.append({"doc_id": best.id, "title": best.title,
                          "source": best.source, "score": None})

    # 2) Augment with semantic neighbours (real value with a real embedder).
    query = f"{label_text} {symptom_text or ''}".strip()
    for chunk, score in retrieve(db, query, crop_id=crop_id, topic="disease", k=k):
        doc = db.get(KnowledgeDoc, chunk.doc_id)
        if doc is None:
            continue
        if best is None:
            best = doc
        if not any(c["doc_id"] == doc.id for c in citations):
            citations.append({"doc_id": doc.id, "title": doc.title,
                              "source": doc.source, "score": round(score, 3)})
    return best, citations
