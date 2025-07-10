from typing import List, Dict, Any, Optional, AsyncIterator
import os
import asyncio
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import get_db, Document as DocumentModel, DocumentChunk
from app.core.vector_store import vector_store
from app.core.logging import get_logger
from app.services.loaders import document_loader_manager, custom_data_loader
from app.services.chunkers import chunker_manager
from app.services.embedders import embedding_manager
from app.services.llm_providers import llm_manager

logger = get_logger(__name__)

class RAGPipeline:
    """Core RAG pipeline orchestrating all components"""
    
    def __init__(self):
        self.document_loader = document_loader_manager
        self.text_chunker = chunker_manager
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store
        self.llm_manager = llm_manager
    
    async def ingest_file(self, file_path: str, source_tool: str = "manual_upload", 
                         metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ingest a file into the RAG system"""
        db = next(get_db())
        
        try:
            # Create document record
            doc_record = DocumentModel(
                filename=Path(file_path).name,
                file_path=file_path,
                source_tool=source_tool,
                content_type=self._get_content_type(file_path),
                file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                status="processing",
                metadata_json=metadata or {}
            )
            
            db.add(doc_record)
            db.commit()
            db.refresh(doc_record)
            
            logger.info("Started file ingestion", 
                       file_path=file_path,
                       document_id=doc_record.id)
            
            # Process the file
            result = await self._process_document(db, doc_record)
            
            return result
            
        except Exception as e:
            logger.error("Failed to ingest file", file_path=file_path, error=str(e))
            
            # Update document status to failed
            if 'doc_record' in locals():
                doc_record.status = "failed"
                doc_record.error_message = str(e)
                db.commit()
            
            raise
        finally:
            db.close()
    
    async def ingest_text(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest text content directly into the RAG system"""
        db = next(get_db())
        
        try:
            # Create document record
            doc_record = DocumentModel(
                filename=metadata.get("filename", "custom_text"),
                source_tool=metadata.get("source_tool", "custom_data"),
                content_type="text/plain",
                file_size=len(text.encode('utf-8')),
                status="processing",
                metadata_json=metadata
            )
            
            db.add(doc_record)
            db.commit()
            db.refresh(doc_record)
            
            logger.info("Started text ingestion", 
                       text_length=len(text),
                       document_id=doc_record.id)
            
            # Process the text
            result = await self._process_text(db, doc_record, text)
            
            return result
            
        except Exception as e:
            logger.error("Failed to ingest text", error=str(e))
            
            # Update document status to failed
            if 'doc_record' in locals():
                doc_record.status = "failed"
                doc_record.error_message = str(e)
                db.commit()
            
            raise
        finally:
            db.close()
    
    async def _process_document(self, db: Session, doc_record: DocumentModel) -> Dict[str, Any]:
        """Process a document file through the RAG pipeline"""
        try:
            # Load document
            documents = self.document_loader.load_document(doc_record.file_path)
            
            # Chunk documents
            chunks = self.text_chunker.chunk_documents(documents)
            
            # Generate embeddings
            texts = [chunk.page_content for chunk in chunks]
            embeddings = self.embedding_manager.embed_texts(texts)
            
            # Prepare metadata for vector store
            metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    "document_id": doc_record.id,
                    "chunk_index": i,
                    "source": doc_record.filename,
                    "source_tool": doc_record.source_tool,
                    **chunk.metadata
                }
                metadatas.append(chunk_metadata)
            
            # Add to vector store
            vector_ids = self.vector_store.add_vectors(texts, embeddings, metadatas)
            
            # Save chunk records
            for i, (chunk, vector_id) in enumerate(zip(chunks, vector_ids)):
                chunk_record = DocumentChunk(
                    document_id=doc_record.id,
                    chunk_index=i,
                    chunk_text=chunk.page_content,
                    chunk_hash=chunk.metadata.get("chunk_hash", ""),
                    vector_id=vector_id,
                    metadata_json=chunk.metadata
                )
                db.add(chunk_record)
            
            # Update document status
            doc_record.status = "indexed"
            doc_record.indexed_at = datetime.utcnow()
            doc_record.chunk_count = len(chunks)
            
            db.commit()
            
            logger.info("Document processed successfully", 
                       document_id=doc_record.id,
                       chunks=len(chunks))
            
            return {
                "document_id": doc_record.id,
                "filename": doc_record.filename,
                "status": "indexed",
                "chunk_count": len(chunks),
                "processing_time": (datetime.utcnow() - doc_record.created_at).total_seconds()
            }
            
        except Exception as e:
            logger.error("Failed to process document", 
                        document_id=doc_record.id, 
                        error=str(e))
            
            doc_record.status = "failed"
            doc_record.error_message = str(e)
            db.commit()
            
            raise
    
    async def _process_text(self, db: Session, doc_record: DocumentModel, text: str) -> Dict[str, Any]:
        """Process text content through the RAG pipeline"""
        try:
            # Create document from text
            document = custom_data_loader.load_from_text(text, doc_record.metadata_json)
            
            # Chunk document
            chunks = self.text_chunker.chunk_documents([document])
            
            # Generate embeddings
            texts = [chunk.page_content for chunk in chunks]
            embeddings = self.embedding_manager.embed_texts(texts)
            
            # Prepare metadata for vector store
            metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    "document_id": doc_record.id,
                    "chunk_index": i,
                    "source": doc_record.filename,
                    "source_tool": doc_record.source_tool,
                    **chunk.metadata
                }
                metadatas.append(chunk_metadata)
            
            # Add to vector store
            vector_ids = self.vector_store.add_vectors(texts, embeddings, metadatas)
            
            # Save chunk records
            for i, (chunk, vector_id) in enumerate(zip(chunks, vector_ids)):
                chunk_record = DocumentChunk(
                    document_id=doc_record.id,
                    chunk_index=i,
                    chunk_text=chunk.page_content,
                    chunk_hash=chunk.metadata.get("chunk_hash", ""),
                    vector_id=vector_id,
                    metadata_json=chunk.metadata
                )
                db.add(chunk_record)
            
            # Update document status
            doc_record.status = "indexed"
            doc_record.indexed_at = datetime.utcnow()
            doc_record.chunk_count = len(chunks)
            
            db.commit()
            
            logger.info("Text processed successfully", 
                       document_id=doc_record.id,
                       chunks=len(chunks))
            
            return {
                "document_id": doc_record.id,
                "filename": doc_record.filename,
                "status": "indexed",
                "chunk_count": len(chunks),
                "processing_time": (datetime.utcnow() - doc_record.created_at).total_seconds()
            }
            
        except Exception as e:
            logger.error("Failed to process text", 
                        document_id=doc_record.id, 
                        error=str(e))
            
            doc_record.status = "failed"
            doc_record.error_message = str(e)
            db.commit()
            
            raise
    
    async def query(self, query: str, top_k: int = 5) -> str:
        """Query the RAG system and get a response"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_manager.embed_text(query)
            
            # Search for relevant chunks
            search_results = self.vector_store.search_vectors(query_embedding, top_k)
            
            # Generate response
            response = await self.llm_manager.generate_response(query, search_results)
            
            logger.info("Query processed successfully", 
                       query_length=len(query),
                       retrieved_chunks=len(search_results),
                       response_length=len(response))
            
            return response
            
        except Exception as e:
            logger.error("Failed to process query", query=query, error=str(e))
            raise
    
    async def query_streaming(self, query: str, top_k: int = 5) -> AsyncIterator[str]:
        """Query the RAG system and get a streaming response"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_manager.embed_text(query)
            
            # Search for relevant chunks
            search_results = self.vector_store.search_vectors(query_embedding, top_k)
            
            # Generate streaming response
            async for chunk in self.llm_manager.generate_streaming_response(query, search_results):
                yield chunk
            
            logger.info("Streaming query processed successfully", 
                       query_length=len(query),
                       retrieved_chunks=len(search_results))
            
        except Exception as e:
            logger.error("Failed to process streaming query", query=query, error=str(e))
            raise
    
    def _get_content_type(self, file_path: str) -> str:
        """Get content type based on file extension"""
        extension = Path(file_path).suffix.lower()
        
        content_types = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".markdown": "text/markdown"
        }
        
        return content_types.get(extension, "application/octet-stream")
    
    def get_document_status(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Get document processing status"""
        db = next(get_db())
        try:
            doc_record = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            if not doc_record:
                return None
            
            return {
                "document_id": doc_record.id,
                "filename": doc_record.filename,
                "status": doc_record.status,
                "chunk_count": doc_record.chunk_count,
                "created_at": doc_record.created_at,
                "indexed_at": doc_record.indexed_at,
                "error_message": doc_record.error_message
            }
        finally:
            db.close()
    
    def delete_document(self, document_id: int) -> bool:
        """Delete a document and its chunks"""
        db = next(get_db())
        try:
            doc_record = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
            if not doc_record:
                return False
            
            # Delete from vector store
            chunk_records = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).all()
            
            vector_ids = [chunk.vector_id for chunk in chunk_records]
            if vector_ids:
                self.vector_store.delete_vectors(vector_ids)
            
            # Delete from database
            db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
            db.query(DocumentModel).filter(DocumentModel.id == document_id).delete()
            db.commit()
            
            logger.info("Document deleted successfully", document_id=document_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete document", document_id=document_id, error=str(e))
            db.rollback()
            return False
        finally:
            db.close()
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of all RAG components"""
        return {
            "vector_store": self.vector_store.health_check(),
            "llm_providers": self.llm_manager.health_check(),
            "embedding_manager": True,  # Always available if initialized
            "document_loader": True,
            "text_chunker": True
        }

# Global instance
rag_pipeline = RAGPipeline() 