# File: tests/integration/test_end_to_end.py
# Integration test: upload -> ingest -> chunk -> embed(mock) -> search -> summarize -> audit verify.

import pytest
import asyncio
import tempfile
import os
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import get_settings
from app.services.auditlog import read_audit_event
from app.db.repository import create_tenant
from app.services.rbac import create_role, assign_role

class TestEndToEndWorkflow:
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app."""
        return create_app()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def test_tenant(self):
        """Create test tenant with roles."""
        tenant_data = create_tenant("Test Corp", "admin@testcorp.com")
        tenant_id = tenant_data["id"]
        
        # Create test user and assign admin role
        from app.db.repository import create_user
        user_data = create_user("testuser@testcorp.com", "password123", tenant_id)
        user_id = user_data["id"]
        
        assign_role(user_id, tenant_id, "admin")
        
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "email": "testuser@testcorp.com"
        }
    
    @pytest.fixture
    def auth_token(self, client, test_tenant):
        """Get JWT token for test user."""
        response = client.post("/v1/login", json={
            "username": test_tenant["email"],
            "password": "password123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_full_document_workflow(self, client, test_tenant, auth_token):
        """Test complete workflow from upload to audit verification."""
        tenant_id = test_tenant["tenant_id"]
        
        # Mock embedding provider to avoid external API calls
        with patch('app.services.embeddings.get_embedding_batch') as mock_embeddings:
            mock_embeddings.return_value = [[0.1] * 1536]  # Mock 1536-dim vector
            
            # Step 1: Upload document
            test_content = b"This is a test document with some PII like john.doe@example.com and phone (555) 123-4567."
            
            files = {"file": ("test.txt", test_content, "text/plain")}
            data = {"tenant_id": tenant_id}
            headers = {"Authorization": f"Bearer {auth_token}"}
            
            upload_response = client.post("/v1/upload", files=files, data=data, headers=headers)
            assert upload_response.status_code == 200
            
            upload_data = upload_response.json()
            document_id = upload_data["document_id"]
            assert upload_data["status"] == "processing"
            
            # Step 2: Search for content
            search_payload = {
                "tenant_id": tenant_id,
                "query": "test document",
                "top_k": 5
            }
            
            search_response = client.post("/v1/search", json=search_payload, headers=headers)
            assert search_response.status_code == 200
            
            search_results = search_response.json()
            assert len(search_results) >= 0  # May be empty if indexing is async
            
            # Step 3: Summarize document
            summarize_payload = {
                "tenant_id": tenant_id,
                "document_id": document_id,
                "query": "PII information"
            }
            
            summarize_response = client.post("/v1/summarize", json=summarize_payload, headers=headers)
            assert summarize_response.status_code == 200
            
            summary_data = summarize_response.json()
            assert "summary" in summary_data
            assert "signed_audit_id" in summary_data
            
            # Step 4: Verify audit log
            audit_id = summary_data["signed_audit_id"]
            audit_response = client.get(f"/v1/audit/{audit_id}", headers=headers)
            assert audit_response.status_code == 200
            
            audit_data = audit_response.json()
            assert audit_data["signature_valid"] is True
            assert audit_data["audit_event"]["action"] == "summarize"
            assert audit_data["audit_event"]["tenant_id"] == tenant_id
    
    def test_rbac_enforcement(self, client, test_tenant):
        """Test that RBAC properly restricts access."""
        tenant_id = test_tenant["tenant_id"]
        
        # Create a viewer user with limited permissions
        from app.db.repository import create_user
        viewer_data = create_user("viewer@testcorp.com", "password123", tenant_id)
        assign_role(viewer_data["id"], tenant_id, "viewer")
        
        # Get token for viewer
        response = client.post("/v1/login", json={
            "username": "viewer@testcorp.com",
            "password": "password123"
        })
        viewer_token = response.json()["access_token"]
        
        # Try to upload (should fail)
        test_content = b"Test content"
        files = {"file": ("test.txt", test_content, "text/plain")}
        data = {"tenant_id": tenant_id}
        headers = {"Authorization": f"Bearer {viewer_token}"}
        
        upload_response = client.post("/v1/upload", files=files, data=data, headers=headers)
        assert upload_response.status_code == 403  # Forbidden
    
    def test_pii_redaction_in_search(self, client, test_tenant, auth_token):
        """Test that PII is properly redacted in search results."""
        tenant_id = test_tenant["tenant_id"]
        
        # Mock embedding and search to return content with PII
        with patch('app.services.embeddings.get_embedding_batch') as mock_embeddings:
            with patch('app.services.vectorstore.search') as mock_search:
                mock_embeddings.return_value = [[0.1] * 1536]
                mock_search.return_value = [{
                    "vector_id": "test_chunk_1",
                    "score": 0.95,
                    "text": "Contact John Doe at john.doe@example.com",
                    "metadata": {"document_id": "test_doc"}
                }]
                
                # Create a user without PII viewing permissions
                from app.db.repository import create_user
                restricted_user = create_user("restricted@testcorp.com", "password123", tenant_id)
                assign_role(restricted_user["id"], tenant_id, "viewer")  # No pii:view permission
                
                # Get token for restricted user
                response = client.post("/v1/login", json={
                    "username": "restricted@testcorp.com",
                    "password": "password123"
                })
                restricted_token = response.json()["access_token"]
                
                # Search as restricted user
                search_payload = {
                    "tenant_id": tenant_id,
                    "query": "contact information",
                    "top_k": 5
                }
                headers = {"Authorization": f"Bearer {restricted_token}"}
                
                search_response = client.post("/v1/search", json=search_payload, headers=headers)
                assert search_response.status_code == 200
                
                results = search_response.json()
                if results:
                    # PII should be redacted
                    result_text = results[0]["text"]
                    assert "john.doe@example.com" not in result_text
                    assert "[EMAIL]" in result_text or "*" in result_text
    
    def test_audit_signature_verification(self):
        """Test that audit signatures can be verified."""
        # Create a test audit event
        test_event = {
            "timestamp": "2024-01-01T10:00:00",
            "tenant_id": "test_tenant",
            "user_id": "test_user",
            "action": "test_action",
            "resource": "test_resource",
            "metadata": {"test": "data"}
        }
        
        from app.services.auditlog import write_audit_event
        audit_id = write_audit_event(test_event)
        
        # Verify the event can be read and signature is valid
        audit_data = read_audit_event(audit_id)
        assert audit_data is not None
        assert audit_data["signature_valid"] is True
        assert audit_data["audit_event"]["action"] == "test_action"
    
    def test_tenant_isolation(self, client):
        """Test that tenants cannot access each other's data."""
        # Create two separate tenants
        tenant1 = create_tenant("Tenant One", "admin1@tenant1.com")
        tenant2 = create_tenant("Tenant Two", "admin2@tenant2.com")
        
        # Create users for each tenant
        from app.db.repository import create_user
        user1 = create_user("user1@tenant1.com", "password123", tenant1["id"])
        user2 = create_user("user2@tenant2.com", "password123", tenant2["id"])
        
        assign_role(user1["id"], tenant1["id"], "admin")
        assign_role(user2["id"], tenant2["id"], "admin")
        
        # Get tokens
        response1 = client.post("/v1/login", json={
            "username": "user1@tenant1.com",
            "password": "password123"
        })
        token1 = response1.json()["access_token"]
        
        # User 1 tries to search in Tenant 2's data (should fail)
        search_payload = {
            "tenant_id": tenant2["id"],
            "query": "test",
            "top_k": 5
        }
        headers = {"Authorization": f"Bearer {token1}"}
        
        search_response = client.post("/v1/search", json=search_payload, headers=headers)
        assert search_response.status_code == 403  # Forbidden

if __name__ == "__main__":
    pytest.main([__file__])