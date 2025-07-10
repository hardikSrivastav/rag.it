from typing import List, Dict, Any
from abc import ABC, abstractmethod
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class BaseEmbedder(ABC):
    """Base class for embedders"""
    
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        pass
    
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        pass
    
    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        pass

class SentenceTransformerEmbedder(BaseEmbedder):
    """Sentence-transformers based embedder"""
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.model = None
        self.dimension = None
        self._load_model()
    
    def _load_model(self):
        """Load the sentence-transformers model"""
        try:
            logger.info("Loading embedding model", model_name=self.model_name)
            
            # Set device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Load model
            self.model = SentenceTransformer(self.model_name, device=device)
            
            # Get dimension
            self.dimension = self.model.get_sentence_embedding_dimension()
            
            logger.info("Embedding model loaded successfully", 
                       model_name=self.model_name,
                       dimension=self.dimension,
                       device=device)
            
        except Exception as e:
            logger.error("Failed to load embedding model", 
                        model_name=self.model_name, 
                        error=str(e))
            raise
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        try:
            if not texts:
                return []
            
            # Generate embeddings
            embeddings = self.model.encode(texts, convert_to_tensor=False)
            
            # Convert to list of lists
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()
            
            logger.info("Generated embeddings", 
                       text_count=len(texts),
                       embedding_dimension=len(embeddings[0]) if embeddings else 0)
            
            return embeddings
            
        except Exception as e:
            logger.error("Failed to generate embeddings", error=str(e))
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            # Generate embedding
            embedding = self.model.encode([text], convert_to_tensor=False)
            
            # Convert to list
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            
            # Return the first (and only) embedding
            return embedding[0] if embedding else []
            
        except Exception as e:
            logger.error("Failed to generate embedding", error=str(e))
            raise
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        return self.dimension

class BatchEmbedder:
    """Batch embedder for efficient processing of large amounts of text"""
    
    def __init__(self, embedder: BaseEmbedder, batch_size: int = 32):
        self.embedder = embedder
        self.batch_size = batch_size
    
    def embed_texts_in_batches(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings in batches for efficiency"""
        try:
            all_embeddings = []
            
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                batch_embeddings = self.embedder.embed_texts(batch_texts)
                all_embeddings.extend(batch_embeddings)
                
                logger.info("Processed batch", 
                           batch_number=i // self.batch_size + 1,
                           batch_size=len(batch_texts),
                           total_processed=len(all_embeddings))
            
            return all_embeddings
            
        except Exception as e:
            logger.error("Failed to generate embeddings in batches", error=str(e))
            raise

class EmbeddingManager:
    """Manager for different embedding models"""
    
    def __init__(self):
        self.embedders = {}
        self.default_embedder = None
        self._initialize_default_embedder()
    
    def _initialize_default_embedder(self):
        """Initialize the default embedder"""
        try:
            self.default_embedder = SentenceTransformerEmbedder()
            self.embedders["default"] = self.default_embedder
            
            logger.info("Default embedder initialized")
            
        except Exception as e:
            logger.error("Failed to initialize default embedder", error=str(e))
            raise
    
    def get_embedder(self, embedder_name: str = "default") -> BaseEmbedder:
        """Get embedder by name"""
        if embedder_name not in self.embedders:
            raise ValueError(f"Unknown embedder: {embedder_name}")
        
        return self.embedders[embedder_name]
    
    def embed_texts(self, texts: List[str], embedder_name: str = "default") -> List[List[float]]:
        """Generate embeddings using specified embedder"""
        embedder = self.get_embedder(embedder_name)
        return embedder.embed_texts(texts)
    
    def embed_text(self, text: str, embedder_name: str = "default") -> List[float]:
        """Generate embedding using specified embedder"""
        embedder = self.get_embedder(embedder_name)
        return embedder.embed_text(text)
    
    def get_embedding_dimension(self, embedder_name: str = "default") -> int:
        """Get embedding dimension"""
        embedder = self.get_embedder(embedder_name)
        return embedder.get_embedding_dimension()
    
    def add_embedder(self, name: str, embedder: BaseEmbedder):
        """Add a new embedder"""
        self.embedders[name] = embedder
        logger.info("Added embedder", name=name)
    
    def get_available_embedders(self) -> List[str]:
        """Get list of available embedders"""
        return list(self.embedders.keys())
    
    def create_batch_embedder(self, batch_size: int = 32, embedder_name: str = "default") -> BatchEmbedder:
        """Create a batch embedder"""
        embedder = self.get_embedder(embedder_name)
        return BatchEmbedder(embedder, batch_size)

# Global instance
embedding_manager = EmbeddingManager() 