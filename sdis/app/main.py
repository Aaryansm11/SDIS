# app/main.py
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import asynccontextmanager
import time
import uuid

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import Base
from app.api.v1.models import HealthResponse, ErrorResponse

# Configure logging first
configure_logging()
logger = get_logger(__name__)

# Database setup
settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=300
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_database() -> Session:
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    
    # Startup
    logger.info("Starting SDIS application")
    
    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    # Verify services
    try:
        # Test database connection
        with SessionLocal() as db:
            db.execute("SELECT 1")
        
        # Test embedding service
        from app.services.embeddings import get_embedding_service
        embedding_service = get_embedding_service()
        test_embeddings = embedding_service.get_embedding_batch(["test"])
        logger.info(f"Embedding service initialized (dim={len(test_embeddings[0])})")
        
        # Test crypto service
        from app.services.crypto_sign import CryptoSignService
        crypto_service = CryptoSignService(
            settings.signing_private_key,
            settings.signing_public_key
        )
        test_signature = crypto_service.sign_payload("test")
        logger.info("Crypto signing service initialized")
        
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        # Don't fail startup for service errors in development
        if settings.env == "production":
            raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down SDIS application")

def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=settings.app_name,
        description="Secure Document Intelligence Service",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.env == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] if settings.env == "development" else ["localhost"]
    )
    
    # Request ID middleware
    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next):
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        correlation_id = getattr(request.state, 'correlation_id', 'unknown')
        
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.detail,
                message=f"HTTP {exc.status_code}",
                correlation_id=correlation_id
            ).dict()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        correlation_id = getattr(request.state, 'correlation_id', 'unknown')
        
        logger.error(f"Unhandled exception: {exc}", extra={
            'correlation_id': correlation_id,
            'path': request.url.path
        })
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal server error",
                message="An unexpected error occurred",
                correlation_id=correlation_id
            ).dict()
        )
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """Health check endpoint"""
        
        services = {}
        
        # Check database
        try:
            with SessionLocal() as db:
                db.execute("SELECT 1")
            services["database"] = "healthy"
        except Exception:
            services["database"] = "unhealthy"
        
        # Check storage
        try:
            import os
            if settings.storage_backend == "local":
                os.makedirs(settings.local_storage_path, exist_ok=True)
            services["storage"] = "healthy"
        except Exception:
            services["storage"] = "unhealthy"
        
        overall_status = "healthy" if all(
            status == "healthy" for status in services.values()
        ) else "degraded"
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version="1.0.0",
            services=services
        )
    
    # Include routers
    from app.api.v1.auth import get_router as auth_router
    from app.api.v1.docs import get_router as docs_router
    from app.api.v1.queries import get_router as queries_router
    from app.api.v1.admin import get_router as admin_router
    
    app.include_router(auth_router(), prefix="/v1")
    app.include_router(docs_router(), prefix="/v1")
    app.include_router(queries_router(), prefix="/v1")
    app.include_router(admin_router(), prefix="/v1")
    
    return app

# Patch the auth router to use our database dependency
def patch_auth_dependencies():
    """Patch auth module dependencies"""
    import app.api.v1.auth as auth_module
    auth_module.get_database = get_database

# Application factory
def get_app() -> FastAPI:
    """Get configured FastAPI application"""
    patch_auth_dependencies()
    return create_app()