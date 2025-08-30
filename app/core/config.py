# app/core/config.py
from pydantic import BaseSettings, Field
from typing import Optional
import os

class Settings(BaseSettings):
    # App metadata
    app_name: str = Field(default="SDIS", env="APP_NAME")
    env: str = Field(default="development", env="ENV")
    debug: bool = Field(default=True)
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # AI/ML
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    embedding_provider: str = Field(default="openai", env="EMBEDDING_PROVIDER")  # openai|hf
    embedding_dim: int = Field(default=1536)  # OpenAI text-embedding-ada-002
    
    # Storage
    vectorstore_path: str = Field(default="/data/faiss", env="VECTORSTORE_PATH")
    storage_backend: str = Field(default="local", env="STORAGE_BACKEND")  # local|s3
    local_storage_path: str = Field(default="/data/documents")
    
    # Security
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_hours: int = Field(default=24)
    
    # Signing keys for audit
    signing_private_key: str = Field(..., env="SIGNING_PRIVATE_KEY")
    signing_public_key: str = Field(..., env="SIGNING_PUBLIC_KEY")
    
    # Audit
    audit_log_path: str = Field(default="/data/audit.log", env="AUDIT_LOG_PATH")
    
    # Processing limits
    max_file_size_mb: int = Field(default=50)
    chunk_size: int = Field(default=1000)
    chunk_overlap: int = Field(default=200)
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Singleton pattern
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings