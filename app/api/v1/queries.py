"""
Query endpoints (search, summarize).
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from uuid import UUID

def get_router() -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["queries"])

    @router.post("/search")
    async def search_text(tenant_id: str, query: str, top_k: int = 5, user_id: Optional[str] = None) -> List[Dict]:
        """
        Search stub: should embed query, search FAISS, and return chunks with metadata.
        """
        return []

    @router.post("/summarize")
    async def summarize_doc(tenant_id: str, document_id: UUID, query: Optional[str] = None, user_id: Optional[str] = None) -> Dict:
        """
        Summarize stub: should perform retrieval, call LLM, write audit event, sign it.
        """
        return {"summary": "", "highlights": [], "signed_audit_id": ""}

    return router
