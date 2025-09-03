# File: scripts/seed_data.py
# Seed database with sample tenants, users, and test data

import asyncio
import os
import sys
from datetime import datetime

# Add app to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.db.repository import create_tenant, create_user
from app.services.rbac import create_role, assign_role
from app.services.vectorstore import create_index
from app.core.config import get_settings
from app.core.logging import configure_logging

def seed_database():
    """Seed the database with sample data for testing."""
    
    configure_logging()
    settings = get_settings()
    
    print("🌱 Seeding SDIS database...")
    
    # Create sample tenants
    tenants = [
        {"name": "Acme Corporation", "admin_email": "admin@acme.com"},
        {"name": "Tech Startup Inc", "admin_email": "admin@techstartup.com"},
        {"name": "Healthcare Systems", "admin_email": "admin@healthcare.com"}
    ]
    
    created_tenants = []
    for tenant_info in tenants:
        print(f"Creating tenant: {tenant_info['name']}")
        tenant = create_tenant(tenant_info["name"], tenant_info["admin_email"])
        created_tenants.append(tenant)
        
        tenant_id = tenant["id"]
        
        # Create vector index for tenant
        create_index(tenant_id, dim=1536)
        print(f"  ✓ Vector index created")
        
        # Create sample users for each tenant
        users = [
            {"email": f"admin@{tenant_info['name'].lower().replace(' ', '')}.com", "role": "admin"},
            {"email": f"editor@{tenant_info['name'].lower().replace(' ', '')}.com", "role": "editor"},
            {"email": f"viewer@{tenant_info['name'].lower().replace(' ', '')}.com", "role": "viewer"},
            {"email": f"analyst@{tenant_info['name'].lower().replace(' ', '')}.com", "role": "analyst"}
        ]
        
        for user_info in users:
            print(f"  Creating user: {user_info['email']}")
            user = create_user(user_info["email"], "password123", tenant_id)
            assign_role(user["id"], tenant_id, user_info["role"])
            print(f"    ✓ Assigned role: {user_info['role']}")
    
    print(f"\n✅ Database seeded successfully!")
    print(f"Created {len(created_tenants)} tenants with users and roles")
    print(f"\nSample login credentials:")
    print(f"  Email: admin@acmecorporation.com")
    print(f"  Password: password123")
    print(f"  Tenant ID: {created_tenants[0]['id']}")
    
    print(f"\nDefault roles created for each tenant:")
    print(f"  - admin: Full permissions including PII access")
    print(f"  - editor: Upload, search, summarize (no PII access)")
    print(f"  - viewer: Search and summarize only")
    print(f"  - analyst: Search, summarize with PII access")

def create_sample_documents():
    """Create sample documents for testing."""
    print("\n📄 Creating sample documents...")
    
    sample_docs = [
        {
            "filename": "employee_handbook.txt",
            "content": """Employee Handbook - Acme Corporation

Welcome to Acme Corporation! This handbook contains important information about our policies.

Contact Information:
- HR Department: hr@acme.com
- Emergency Contact: (555) 123-4567
- Main Office: 123 Business Ave, Business City, BC 12345

Employee Benefits:
Our comprehensive benefits package includes health insurance, retirement plans, and paid time off.

Data Security:
All employees must protect confidential information including customer data, financial records, and personal information.

For questions, contact your manager or HR representative John Smith at john.smith@acme.com.
"""
        },
        {
            "filename": "financial_report.txt", 
            "content": """Q4 Financial Report - Confidential

Revenue Performance:
Total revenue for Q4 increased by 15% compared to previous quarter.

Key Metrics:
- Customer acquisition cost decreased
- Monthly recurring revenue grew significantly
- Churn rate remained stable at industry averages

Contact CFO Sarah Johnson (sarah.johnson@acme.com) for detailed analysis.

Account Information:
Primary business account: ****-****-****-1234
Tax ID: 12-3456789

This document contains confidential financial information and should not be shared externally.
"""
        }
    ]
    
    # In a real implementation, you would upload these through the API
    print(f"Sample documents prepared:")
    for doc in sample_docs:
        print(f"  - {doc['filename']} ({len(doc['content'])} characters)")
    
    print("💡 To upload these documents, use the /v1/upload endpoint with proper authentication.")

if __name__ == "__main__":
    try:
        seed_database()
        create_sample_documents()
        print(f"\n🚀 SDIS is ready for testing!")
        print(f"Start the server with: uvicorn app.main:app --reload")
        
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        sys.exit(1)