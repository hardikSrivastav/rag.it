from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from qdrant_client.http.exceptions import UnexpectedResponse
import uuid
import hashlib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class QdrantVectorStore:
    """Qdrant vector store wrapper for RAG operations"""
    
    def __init__(self):
        self.client = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.dimension = settings.EMBEDDING_DIMENSION
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Qdrant client"""
        try:
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY,
                timeout=60
            )
            logger.info("Qdrant client initialized", 
                       host=settings.QDRANT_HOST, 
                       port=settings.QDRANT_PORT)
            
            # Ensure collection exists
            self._ensure_collection()
            
        except Exception as e:
            logger.error("Failed to initialize Qdrant client", error=str(e))
            raise
    
    def _ensure_collection(self):
        """Ensure the collection exists, create if it doesn't"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                logger.info("Creating Qdrant collection", collection_name=self.collection_name)
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension,
                        distance=Distance.COSINE
                    )
                )
                logger.info("Collection created successfully", collection_name=self.collection_name)
            else:
                logger.info("Collection already exists", collection_name=self.collection_name)
                
        except Exception as e:
            logger.error("Failed to ensure collection", error=str(e))
            raise
    
    def add_vectors(self, texts: List[str], vectors: List[List[float]], 
                   metadatas: List[Dict[str, Any]]) -> List[str]:
        """Add vectors to the collection"""
        try:
            points = []
            vector_ids = []
            
            for i, (text, vector, metadata) in enumerate(zip(texts, vectors, metadatas)):
                # Generate unique ID for the vector
                vector_id = str(uuid.uuid4())
                vector_ids.append(vector_id)
                
                # Create payload with text and metadata
                payload = {
                    "text": text,
                    "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                    **metadata
                }
                
                # Create point
                point = PointStruct(
                    id=vector_id,
                    vector=vector,
                    payload=payload
                )
                points.append(point)
            
            # Upload points
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info("Added vectors to collection", 
                       count=len(points), 
                       collection_name=self.collection_name)
            
            return vector_ids
            
        except Exception as e:
            logger.error("Failed to add vectors", error=str(e))
            raise
    
    def search_vectors(self, query_vector: List[float], top_k: int = 5, 
                      filter_conditions: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors"""
        try:
            # Build filter if provided
            search_filter = None
            if filter_conditions:
                filter_conditions_list = []
                for key, value in filter_conditions.items():
                    filter_conditions_list.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
                search_filter = Filter(must=filter_conditions_list)
            
            # Perform search
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=search_filter,
                with_payload=True,
                with_vectors=False
            )
            
            # Format results
            results = []
            for hit in search_result:
                result = {
                    "id": hit.id,
                    "score": hit.score,
                    "text": hit.payload.get("text", ""),
                    "metadata": {k: v for k, v in hit.payload.items() if k not in ["text", "content_hash"]}
                }
                results.append(result)
            
            logger.info("Search completed", 
                       query_results=len(results), 
                       top_k=top_k)
            
            return results
            
        except Exception as e:
            logger.error("Failed to search vectors", error=str(e))
            raise
    
    def delete_vectors(self, vector_ids: List[str]) -> bool:
        """Delete vectors by IDs"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=vector_ids
            )
            
            logger.info("Deleted vectors", count=len(vector_ids))
            return True
            
        except Exception as e:
            logger.error("Failed to delete vectors", error=str(e))
            return False
    
    def delete_by_filter(self, filter_conditions: Dict[str, Any]) -> bool:
        """Delete vectors by filter conditions"""
        try:
            filter_conditions_list = []
            for key, value in filter_conditions.items():
                filter_conditions_list.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            
            delete_filter = Filter(must=filter_conditions_list)
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=delete_filter
            )
            
            logger.info("Deleted vectors by filter", filter_conditions=filter_conditions)
            return True
            
        except Exception as e:
            logger.error("Failed to delete vectors by filter", error=str(e))
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection information"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "name": collection_info.config.collection_name,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance,
                "points_count": collection_info.points_count,
                "status": collection_info.status
            }
        except Exception as e:
            logger.error("Failed to get collection info", error=str(e))
            return {}
    
    def health_check(self) -> bool:
        """Check if Qdrant is healthy"""
        try:
            collections = self.client.get_collections()
            return True
        except Exception as e:
            logger.error("Qdrant health check failed", error=str(e))
            return False

# Global instance
vector_store = QdrantVectorStore() 