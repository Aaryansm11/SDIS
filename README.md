# Secure Document Intelligence Service (SDIS)

> Enterprise-grade secure RAG + redaction + RBAC + immutable audit logging microservice

## Overview

SDIS is a production-ready document intelligence platform that provides secure document ingestion, PII redaction, embedding-based search, and comprehensive audit logging. Built with multi-tenancy, role-based access control, and cryptographic signing for enterprise compliance.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│  Auth Router  │  Docs Router  │  Query Router  │  Admin     │
├─────────────────────────────────────────────────────────────┤
│             Security & Middleware Layer                     │
│  • JWT Authentication  • RBAC  • Rate Limiting  • CORS     │
├─────────────────────────────────────────────────────────────┤
│                    Service Layer                           │
│  Ingestion  │  Embeddings  │  Vectorstore  │  Redaction    │
│             │  (OpenAI/HF)  │   (FAISS)     │   (spaCy)     │
├─────────────────────────────────────────────────────────────┤
│              Audit & Crypto Layer                          │
│  • Immutable Logging  • Digital Signatures  • Event Trail  │
├─────────────────────────────────────────────────────────────┤
│                  Data Persistence                          │
│  PostgreSQL  │  FAISS Indices  │  File Storage  │  Audit   │
│   (Metadata) │  (Per-tenant)   │  (Local/S3)    │   Logs   │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Features

### Core Capabilities
- **Multi-tenant Document Processing**: Secure per-tenant document isolation
- **Intelligent Text Extraction**: PDF, DOCX, and TXT file support
- **PII/PHI Detection & Redaction**: HIPAA-compliant data protection
- **Semantic Search**: Vector embeddings with similarity search
- **Document Summarization**: AI-powered content analysis
- **Immutable Audit Trail**: Cryptographically signed event logging

### Security & Compliance
- **Role-Based Access Control (RBAC)**: Granular permission system
- **JWT Authentication**: Secure token-based auth
- **Digital Signatures**: RSA/ECDSA signing for audit integrity
- **Input Validation**: Comprehensive request sanitization
- **Rate Limiting**: DDoS protection and resource management

### Enterprise Features
- **Horizontal Scaling**: Stateless service design
- **Pluggable Providers**: OpenAI, HuggingFace, or custom embeddings
- **Storage Flexibility**: Local filesystem or S3-compatible storage
- **Health Monitoring**: Built-in health checks and metrics
- **Docker Support**: Complete containerization

## 📋 Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Docker & Docker Compose (for development)
- OpenAI API key or HuggingFace access (for embeddings)

## 🛠️ Installation

### Development Setup

1. **Clone and Setup Environment**
```bash
git clone <repository>
cd sdis
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start Dependencies**
```bash
# Start PostgreSQL and Redis
docker-compose up postgres redis -d

# Or use local installations
```

4. **Database Setup**
```bash
# Run migrations
make migrate

# Seed initial data
make seed-db
```

5. **Download Language Models**
```bash
# For PII detection
python -m spacy download en_core_web_sm
```

6. **Start Development Server**
```bash
make dev
# Or: uvicorn app.main:app --reload --port 8000
```

### Production Deployment

1. **Docker Deployment**
```bash
# Build and deploy all services
docker-compose up -d

# Scale the application
docker-compose up -d --scale app=3
```

2. **AWS ECS Deployment**
```bash
# Build and push image
make docker-build
make docker-push

# Deploy task definition (customize infra/ecs-task-definition.json)
aws ecs update-service --cluster sdis --service sdis-app
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_NAME` | Application name | `SDIS` | No |
| `ENV` | Environment mode | `development` | No |
| `DATABASE_URL` | PostgreSQL connection | - | Yes |
| `OPENAI_API_KEY` | OpenAI API key | - | If using OpenAI |
| `EMBEDDING_PROVIDER` | Provider type | `openai` | No |
| `VECTORSTORE_PATH` | FAISS storage path | `/data/faiss` | No |
| `JWT_SECRET` | JWT signing secret | - | Yes |
| `SIGNING_PRIVATE_KEY` | RSA private key (PEM) | - | Yes |
| `SIGNING_PUBLIC_KEY` | RSA public key (PEM) | - | Yes |
| `AUDIT_LOG_PATH` | Audit log file path | `/data/audit.log` | No |
| `STORAGE_BACKEND` | Storage type | `local` | No |
| `AWS_S3_BUCKET` | S3 bucket name | - | If using S3 |

### Sample Configuration

```env
# .env
APP_NAME=SDIS
ENV=development
DATABASE_URL=postgresql://sdis:password@localhost:5432/sdis_db
OPENAI_API_KEY=sk-your-openai-key
EMBEDDING_PROVIDER=openai
VECTORSTORE_PATH=/data/faiss
JWT_SECRET=your-super-secret-jwt-key
SIGNING_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
SIGNING_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
AUDIT_LOG_PATH=/data/audit.log
STORAGE_BACKEND=local
MAX_FILE_SIZE_MB=50
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## 📖 API Usage

### Authentication

```bash
# Login to get JWT token
curl -X POST "http://localhost:8000/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@tenant1.com", "password": "password"}'

# Response
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

### Document Upload

```bash
# Upload document
curl -X POST "http://localhost:8000/v1/docs/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "tenant_id=tenant1" \
  -F "file=@document.pdf"

# Response
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant1",
  "status": "processing"
}
```

### Document Search

```bash
# Search documents
curl -X POST "http://localhost:8000/v1/queries/search" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "tenant1",
    "query": "machine learning algorithms",
    "top_k": 5
  }'

# Response
[
  {
    "chunk_id": "chunk_123",
    "score": 0.95,
    "text": "Machine learning algorithms are computational methods...",
    "metadata": {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "page": 1,
      "filename": "ml_research.pdf"
    }
  }
]
```

### Document Summarization

```bash
# Summarize document
curl -X POST "http://localhost:8000/v1/queries/summarize" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "tenant1",
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "What are the main findings?"
  }'

# Response
{
  "summary": "The document presents three key findings about machine learning...",
  "highlights": [
    "Neural networks achieve 95% accuracy on the test dataset",
    "Training time reduced by 40% using new optimization technique"
  ],
  "signed_audit_id": "audit_789abc"
}
```

### Audit Trail Verification

```bash
# Verify audit event
curl -X GET "http://localhost:8000/v1/audit/audit_789abc" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response
{
  "audit_event": {
    "audit_id": "audit_789abc",
    "timestamp": "2025-08-30T10:30:00Z",
    "tenant_id": "tenant1",
    "user_id": "user_456",
    "action": "summarize_document",
    "resource": "document:550e8400-e29b-41d4-a716-446655440000",
    "metadata": {...}
  },
  "signature_valid": true
}
```

## 🔧 Development

### Project Structure

```
sdis/
├── app/
│   ├── main.py                 # FastAPI application factory
│   ├── core/
│   │   ├── config.py          # Settings and configuration
│   │   └── logging.py         # Structured logging setup
│   ├── api/v1/
│   │   ├── models.py          # Pydantic request/response models
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── docs.py            # Document upload endpoints
│   │   ├── queries.py         # Search and summarize endpoints
│   │   ├── admin.py           # Admin management endpoints
│   │   ├── audit.py           # Audit trail endpoints
│   │   └── health.py          # Health check endpoints
│   ├── db/
│   │   ├── models.py          # SQLAlchemy ORM models
│   │   └── repository.py      # Database repository layer
│   ├── services/
│   │   ├── ingestion.py       # File processing and extraction
│   │   ├── chunking.py        # Text chunking for embeddings
│   │   ├── redaction.py       # PII detection and redaction
│   │   ├── embeddings.py      # Embedding provider abstraction
│   │   ├── vectorstore.py     # FAISS vector operations
│   │   ├── rbac.py            # Role-based access control
│   │   ├── auditlog.py        # Audit event logging
│   │   └── crypto_sign.py     # Digital signature utilities
│   ├── utils/
│   │   ├── text.py            # Text processing utilities
│   │   ├── validators.py      # Input validation functions
│   │   └── middleware.py      # Security middleware
│   └── exceptions/
│       └── handlers.py        # Custom exception handlers
├── tests/
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── conftest.py           # Pytest configuration
├── infra/
│   ├── Dockerfile            # Container definition
│   ├── docker-compose.yml    # Local development environment
│   └── alembic/              # Database migrations
├── scripts/
│   └── seed_db.py           # Database seeding script
├── requirements.txt          # Python dependencies
├── Makefile                 # Development commands
└── .env.example             # Environment template
```

### Available Make Commands

```bash
# Development
make dev              # Start development server
make test             # Run all tests
make test-unit        # Run unit tests only
make test-integration # Run integration tests only
make lint             # Run code linting
make format           # Format code with black

# Database
make migrate          # Run database migrations
make seed-db          # Seed database with sample data
make reset-db         # Reset database (destructive)

# Docker
make docker-build     # Build Docker image
make docker-run       # Run in Docker
make docker-clean     # Clean Docker resources

# Production
make docker-push      # Push to registry
make deploy-staging   # Deploy to staging
make deploy-prod      # Deploy to production
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/unit/test_chunking.py -v

# Run integration tests (requires database)
pytest tests/integration/ -v
```

## 🔐 Security Features

### PII/PHI Redaction
- **Automatic Detection**: Email addresses, phone numbers, SSNs, credit cards
- **Redaction Modes**: 
  - `mask`: Replace with `[REDACTED]`
  - `hash`: Deterministic hashing for matching
  - `remove`: Complete removal
- **Compliance**: HIPAA and GDPR ready

### Access Control
- **Multi-tenant Isolation**: Complete data separation
- **Role-based Permissions**: 
  - `admin`: Full tenant access
  - `editor`: Upload and search documents
  - `viewer`: Search only
  - `auditor`: Read audit logs
- **JWT Authentication**: Secure stateless tokens

### Audit & Compliance
- **Immutable Logging**: Append-only audit trail
- **Digital Signatures**: RSA/ECDSA event signing
- **Event Tracking**: All actions logged with metadata
- **Verification**: Cryptographic integrity checks

## 🏢 Multi-tenancy

### Tenant Management
```python
# Create new tenant
POST /v1/admin/tenants
{
  "name": "Acme Corp",
  "admin_email": "admin@acme.com"
}

# Response includes tenant_id and default roles
```

### Data Isolation
- **Database**: Tenant-scoped queries
- **Vector Indices**: Separate FAISS index per tenant
- **File Storage**: Tenant-prefixed storage paths
- **Audit Logs**: Tenant-filtered event access

## 🤖 AI/ML Pipeline

### Document Processing Flow
1. **Upload** → File validation and storage
2. **Extract** → Text extraction (PDF/DOCX/TXT)
3. **Clean** → Text normalization and preprocessing
4. **Redact** → PII detection and redaction
5. **Chunk** → Split into embedding-ready segments
6. **Embed** → Generate vector representations
7. **Index** → Store in per-tenant FAISS index
8. **Audit** → Log all operations with signatures

### Embedding Providers
- **OpenAI**: `text-embedding-ada-002` (default)
- **HuggingFace**: `sentence-transformers/all-MiniLM-L6-v2`
- **Custom**: Implement `EmbeddingProvider` interface

### Vector Search
- **FAISS IndexFlatIP**: Cosine similarity search
- **Per-tenant Indices**: Isolated vector spaces
- **Metadata Integration**: Rich search result context
- **Persistence**: Atomic index saves with backup

## 📊 Monitoring & Operations

### Health Checks
```bash
# Application health
GET /health

# Detailed component status
GET /health/detailed
```

### Metrics & Logging
- **Structured Logging**: JSON format with correlation IDs
- **Performance Metrics**: Request timing and resource usage
- **Error Tracking**: Comprehensive exception handling
- **Audit Analytics**: Searchable compliance reports

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migrations
alembic downgrade -1
```

## 🔧 Configuration Examples

### Local Development
```env
ENV=development
DATABASE_URL=postgresql://sdis:password@localhost:5432/sdis_db
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
VECTORSTORE_PATH=./data/faiss
STORAGE_BACKEND=local
LOG_LEVEL=DEBUG
```

### Production
```env
ENV=production
DATABASE_URL=postgresql://user:pass@prod-db:5432/sdis
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-your-prod-key
VECTORSTORE_PATH=/app/data/faiss
STORAGE_BACKEND=s3
AWS_S3_BUCKET=sdis-documents-prod
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=100
```

## 📈 Performance & Scaling

### Optimization Features
- **Async Operations**: Non-blocking I/O throughout
- **Batch Processing**: Efficient embedding generation
- **Connection Pooling**: Database connection optimization
- **Caching**: Redis-based response caching
- **Lazy Loading**: On-demand resource initialization

### Scaling Considerations
- **Stateless Design**: Horizontal scaling ready
- **Database Indexing**: Optimized queries with proper indices
- **Vector Index Sharding**: Large dataset support
- **Background Tasks**: Async document processing
- **Load Balancing**: Multiple app instances supported

## 🧪 Testing

### Test Coverage
- **Unit Tests**: Core business logic (85%+ coverage)
- **Integration Tests**: End-to-end workflows
- **Performance Tests**: Load testing scenarios
- **Security Tests**: Authentication and authorization

### Test Data
```bash
# Generate test documents
make generate-test-data

# Run performance tests
make test-performance

# Security audit
make test-security
```

## 🚨 Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check PostgreSQL status
docker-compose ps postgres

# View logs
docker-compose logs postgres

# Reset database
make reset-db
```

#### Embedding Provider Issues
```bash
# Test OpenAI connection
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models

# Switch to HuggingFace
export EMBEDDING_PROVIDER=hf
```

#### FAISS Index Corruption
```bash
# Rebuild all indices
POST /v1/admin/reindex
{"tenant_id": "your-tenant"}

# Manual index cleanup
rm -rf /data/faiss/tenant_*
```

### Debug Mode
```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG

# Run with debugger
python -m pdb app/main.py
```

## 🔒 Security Best Practices

### Key Management
- Store private keys in secure key management (AWS KMS, HashiCorp Vault)
- Rotate signing keys periodically
- Use environment-specific key pairs

### Network Security
- Run behind reverse proxy (nginx, CloudFlare)
- Enable HTTPS in production
- Configure proper CORS policies
- Implement rate limiting per client

### Data Protection
- Encrypt sensitive data at rest
- Use secure file permissions (600 for keys)
- Implement data retention policies
- Regular security audits

## 📄 API Documentation

### Interactive Documentation
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### Authentication Flow
1. **Login**: POST `/v1/auth/login` with credentials
2. **Get Token**: Receive JWT access token
3. **Use Token**: Include in `Authorization: Bearer <token>` header
4. **Refresh**: POST `/v1/auth/refresh` before expiration

### Core Endpoints
- `POST /v1/docs/upload` - Upload documents
- `POST /v1/queries/search` - Semantic search
- `POST /v1/queries/summarize` - Document summarization
- `GET /v1/audit/{audit_id}` - Audit event verification
- `POST /v1/admin/tenants` - Tenant management

## 🤝 Contributing

### Development Workflow
1. Create feature branch from `main`
2. Implement changes with tests
3. Run `make lint` and `make test`
4. Submit pull request with description
5. Code review and merge

### Code Standards
- **Type Hints**: All functions must include type annotations
- **Docstrings**: Google-style docstrings for public functions
- **Error Handling**: Comprehensive exception handling
- **Testing**: 80%+ test coverage required
- **Security**: Security review for all changes

## 📞 Support

### Documentation
- **API Reference**: `/docs` endpoint
- **Architecture Docs**: `docs/` directory
- **Deployment Guide**: `docs/deployment.md`

### Getting Help
- **Issues**: GitHub Issues for bugs and features
- **Discussions**: GitHub Discussions for questions
- **Security**: security@company.com for vulnerabilities

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🏷️ Version

Current Version: **1.0.0**

- ✅ Core document intelligence features
- ✅ Multi-tenant architecture
- ✅ Comprehensive security controls
- ✅ Production-ready deployment
- ✅ Full API documentation
- ✅ Complete test suite

---

**SDIS** - Secure Document Intelligence Service
Built with ❤️ for enterprise document processing