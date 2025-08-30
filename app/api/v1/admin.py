"""
Admin endpoints (tenant mgmt, reindex)
"""
from fastapi import APIRouter

def get_router() -> APIRouter:
    router = APIRouter(prefix="/v1/admin", tags=["admin"])

    @router.post("/create-tenant")
    async def create_tenant(name: str, admin_email: str):
        return {"tenant_id": "tenant_dummy", "name": name, "admin": admin_email}

    @router.post("/reindex")
    async def reindex_tenant(tenant_id: str):
        return {"status": "reindex_started", "tenant_id": tenant_id}

    return router
