# app/services/embeddings.py
from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""
    
    @abstractmethod
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        pass
    
    @abstractmethod
    def get_embedding_dim(self) -> int:
        """Get the dimension of embeddings"""
        pass

class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing"""
    
    def __init__(self, dim: int = 1536):
        self.dim = dim
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate random embeddings for testing"""
        import random
        random.seed(42)  # Deterministic for testing
        
        embeddings = []
        for text in texts:
            # Generate pseudo-random vector based on text hash
            text_hash = hash(text)
            random.seed(text_hash)
            vector = [random.gauss(0, 1) for _ in range(self.dim)]
            
            # Normalize vector
            norm = sum(x*x for x in vector) ** 0.5
            if norm > 0:
                vector = [x/norm for x in vector]
            
            embeddings.append(vector)
        
        logger.info(f"Generated {len(embeddings)} mock embeddings")
        return embeddings
    
    def get_embedding_dim(self) -> int:
        return self.dim

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider"""
    
    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        self.api_key = api_key
        self.model = model
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize OpenAI client"""
        try:
            import openai
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            logger.error("OpenAI library not installed")
            raise RuntimeError("OpenAI library required for OpenAI embeddings")
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from OpenAI API"""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")
        
        try:
            # Process in batches to respect rate limits
            batch_size = 100
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            
            logger.info(f"Generated {len(all_embeddings)} OpenAI embeddings")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}")
    
    def get_embedding_dim(self) -> int:
        return 1536  # text-embedding-ada-002 dimension

class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """HuggingFace transformers embedding provider"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self._init_model()
    
    def _init_model(self):
        """Initialize HuggingFace model"""
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            
        except ImportError:
            logger.error("Transformers library not installed")
            raise RuntimeError("Transformers library required for HF embeddings")
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from HuggingFace model"""
        import torch
        
        embeddings = []
        batch_size = 32
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Tokenize
            inputs = self.tokenizer(
                batch, 
                padding=True, 
                truncation=True, 
                return_tensors="pt",
                max_length=512
            ).to(self.device)
            
            # Generate embeddings
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Mean pooling
                embeddings_batch = outputs.last_hidden_state.mean(dim=1)
                # Normalize
                embeddings_batch = torch.nn.functional.normalize(embeddings_batch, p=2, dim=1)
                
                embeddings.extend(embeddings_batch.cpu().numpy().tolist())
        
        logger.info(f"Generated {len(embeddings)} HuggingFace embeddings")
        return embeddings
    
    def get_embedding_dim(self) -> int:
        return 384  # all-MiniLM-L6-v2 dimension

class EmbeddingService:
    """Main embedding service with provider abstraction"""
    
    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self.settings = get_settings()
        
        if provider:
            self.provider = provider
        else:
            self.provider = self._create_provider()
    
    def _create_provider(self) -> EmbeddingProvider:
        """Create embedding provider based on configuration"""
        provider_type = self.settings.embedding_provider.lower()
        
        if provider_type == "mock":
            return MockEmbeddingProvider(self.settings.embedding_dim)
        elif provider_type == "openai":
            if not self.settings.openai_api_key:
                logger.warning("OpenAI API key not configured, using mock provider")
                return MockEmbeddingProvider()
            return OpenAIEmbeddingProvider(self.settings.openai_api_key)
        elif provider_type == "hf":
            return HuggingFaceEmbeddingProvider()
        else:
            logger.warning(f"Unknown provider '{provider_type}', using mock")
            return MockEmbeddingProvider()
    
    def get_embedding_batch(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for a batch of texts"""
        if not texts:
            return []
        
        # Filter empty texts
        filtered_texts = [text.strip() for text in texts if text.strip()]
        if not filtered_texts:
            return []
        
        return self.provider.get_embeddings(filtered_texts)
    
    def get_embedding_dim(self) -> int:
        """Get embedding dimension"""
        return self.provider.get_embedding_dim()

# Module-level service instance
_embedding_service: Optional[EmbeddingService] = None

def get_embedding_service() -> EmbeddingService:
    """Get singleton embedding service"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

def get_embedding_batch(texts: List[str]) -> List[List[float]]:
    """Module-level function to get embeddings"""
    service = get_embedding_service()
    return service.get_embedding_batch(texts)