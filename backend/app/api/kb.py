"""Knowledge base admin endpoints (Phase 2 surface; minimal here).

Docs are authored/validated by agronomy partners via the admin portal. Only
'validated' docs are retrievable by the Crop Doctor (traceability). Reindex
rebuilds a doc's chunks + embeddings.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.api.schemas import KbDocIn, KbDocOut, KbDocPatch
from app.db.base import get_db
from app.db.models import KnowledgeDoc, StaffUser
from app.services import audit, kb_rag

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.get("/docs", response_model=list[KbDocOut])
def list_docs(db: Session = Depends(get_db),
              staff: StaffUser = Depends(require_staff("admin"))):
    return list(db.scalars(select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc())))


@router.post("/docs", response_model=KbDocOut, status_code=201)
def create_doc(body: KbDocIn, db: Session = Depends(get_db),
               staff: StaffUser = Depends(require_staff("admin"))):
    doc = KnowledgeDoc(**body.model_dump())
    db.add(doc)
    db.flush()
    if doc.status == "validated":
        kb_rag.ingest(db, doc)
    audit.record(db, actor_id=staff.id, actor_role=staff.role,
                 action="create", entity="kb_doc", entity_id=doc.id)
    db.commit()
    return doc


@router.patch("/docs/{doc_id}", response_model=KbDocOut)
def patch_doc(doc_id: str, body: KbDocPatch, db: Session = Depends(get_db),
              staff: StaffUser = Depends(require_staff("admin"))):
    doc = db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, "Doc not found")
    changes = body.model_dump(exclude_none=True)
    if "body" in changes:
        doc.version += 1
    for k, v in changes.items():
        setattr(doc, k, v)
    db.flush()
    if doc.status == "validated":
        kb_rag.ingest(db, doc)  # keep the index in sync on validate/edit
    audit.record(db, actor_id=staff.id, actor_role=staff.role,
                 action="update", entity="kb_doc", entity_id=doc.id)
    db.commit()
    return doc


@router.post("/docs/{doc_id}:reindex")
def reindex(doc_id: str, db: Session = Depends(get_db),
            staff: StaffUser = Depends(require_staff("admin"))):
    doc = db.get(KnowledgeDoc, doc_id)
    if not doc:
        raise HTTPException(404, "Doc not found")
    n = kb_rag.ingest(db, doc)
    db.commit()
    return {"doc_id": doc_id, "chunks": n}
