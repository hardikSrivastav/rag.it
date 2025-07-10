from typing import List, Dict, Any
from abc import ABC, abstractmethod
import hashlib

from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter
)
from langchain.schema import Document

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class BaseTextChunker(ABC):
    """Base class for text chunkers"""
    
    @abstractmethod
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk documents into smaller pieces"""
        pass
    
    @abstractmethod
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Document]:
        """Chunk text into smaller pieces"""
        pass

class RecursiveTextChunker(BaseTextChunker):
    """Recursive character text chunker - best for most documents"""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk documents into smaller pieces"""
        try:
            chunked_documents = []
            
            for doc in documents:
                chunks = self.text_splitter.split_documents([doc])
                
                # Add chunk metadata
                for i, chunk in enumerate(chunks):
                    chunk.metadata.update({
                        "chunk_index": i,
                        "chunk_size": len(chunk.page_content),
                        "chunk_hash": hashlib.sha256(chunk.page_content.encode()).hexdigest(),
                        "chunker": "RecursiveTextChunker",
                        "original_document": doc.metadata.get("source", "unknown")
                    })
                
                chunked_documents.extend(chunks)
            
            logger.info("Documents chunked successfully", 
                       input_documents=len(documents),
                       output_chunks=len(chunked_documents),
                       chunker="RecursiveTextChunker")
            
            return chunked_documents
            
        except Exception as e:
            logger.error("Failed to chunk documents", error=str(e))
            raise
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Document]:
        """Chunk text into smaller pieces"""
        try:
            metadata = metadata or {}
            
            # Create document from text
            document = Document(page_content=text, metadata=metadata)
            
            # Chunk the document
            chunks = self.text_splitter.split_documents([document])
            
            # Add chunk metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "chunk_index": i,
                    "chunk_size": len(chunk.page_content),
                    "chunk_hash": hashlib.sha256(chunk.page_content.encode()).hexdigest(),
                    "chunker": "RecursiveTextChunker"
                })
            
            logger.info("Text chunked successfully", 
                       input_length=len(text),
                       output_chunks=len(chunks))
            
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk text", error=str(e))
            raise

class CharacterTextChunker(BaseTextChunker):
    """Character-based text chunker"""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None, separator: str = "\n\n"):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.separator = separator
        
        self.text_splitter = CharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separator=self.separator
        )
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk documents into smaller pieces"""
        try:
            chunked_documents = []
            
            for doc in documents:
                chunks = self.text_splitter.split_documents([doc])
                
                # Add chunk metadata
                for i, chunk in enumerate(chunks):
                    chunk.metadata.update({
                        "chunk_index": i,
                        "chunk_size": len(chunk.page_content),
                        "chunk_hash": hashlib.sha256(chunk.page_content.encode()).hexdigest(),
                        "chunker": "CharacterTextChunker",
                        "separator": self.separator,
                        "original_document": doc.metadata.get("source", "unknown")
                    })
                
                chunked_documents.extend(chunks)
            
            logger.info("Documents chunked successfully", 
                       input_documents=len(documents),
                       output_chunks=len(chunked_documents),
                       chunker="CharacterTextChunker")
            
            return chunked_documents
            
        except Exception as e:
            logger.error("Failed to chunk documents", error=str(e))
            raise
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Document]:
        """Chunk text into smaller pieces"""
        try:
            metadata = metadata or {}
            
            # Create document from text
            document = Document(page_content=text, metadata=metadata)
            
            # Chunk the document
            chunks = self.text_splitter.split_documents([document])
            
            # Add chunk metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "chunk_index": i,
                    "chunk_size": len(chunk.page_content),
                    "chunk_hash": hashlib.sha256(chunk.page_content.encode()).hexdigest(),
                    "chunker": "CharacterTextChunker",
                    "separator": self.separator
                })
            
            logger.info("Text chunked successfully", 
                       input_length=len(text),
                       output_chunks=len(chunks))
            
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk text", error=str(e))
            raise

class TokenTextChunker(BaseTextChunker):
    """Token-based text chunker"""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        self.text_splitter = TokenTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk documents into smaller pieces"""
        try:
            chunked_documents = []
            
            for doc in documents:
                chunks = self.text_splitter.split_documents([doc])
                
                # Add chunk metadata
                for i, chunk in enumerate(chunks):
                    chunk.metadata.update({
                        "chunk_index": i,
                        "chunk_size": len(chunk.page_content),
                        "chunk_hash": hashlib.sha256(chunk.page_content.encode()).hexdigest(),
                        "chunker": "TokenTextChunker",
                        "original_document": doc.metadata.get("source", "unknown")
                    })
                
                chunked_documents.extend(chunks)
            
            logger.info("Documents chunked successfully", 
                       input_documents=len(documents),
                       output_chunks=len(chunked_documents),
                       chunker="TokenTextChunker")
            
            return chunked_documents
            
        except Exception as e:
            logger.error("Failed to chunk documents", error=str(e))
            raise
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Document]:
        """Chunk text into smaller pieces"""
        try:
            metadata = metadata or {}
            
            # Create document from text
            document = Document(page_content=text, metadata=metadata)
            
            # Chunk the document
            chunks = self.text_splitter.split_documents([document])
            
            # Add chunk metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "chunk_index": i,
                    "chunk_size": len(chunk.page_content),
                    "chunk_hash": hashlib.sha256(chunk.page_content.encode()).hexdigest(),
                    "chunker": "TokenTextChunker"
                })
            
            logger.info("Text chunked successfully", 
                       input_length=len(text),
                       output_chunks=len(chunks))
            
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk text", error=str(e))
            raise

class TextChunkerManager:
    """Manager for different text chunkers"""
    
    def __init__(self):
        self.chunkers = {
            "recursive": RecursiveTextChunker(),
            "character": CharacterTextChunker(),
            "token": TokenTextChunker()
        }
        self.default_chunker = "recursive"
    
    def chunk_documents(self, documents: List[Document], chunker_type: str = None) -> List[Document]:
        """Chunk documents using specified chunker"""
        chunker_type = chunker_type or self.default_chunker
        
        if chunker_type not in self.chunkers:
            raise ValueError(f"Unknown chunker type: {chunker_type}")
        
        chunker = self.chunkers[chunker_type]
        return chunker.chunk_documents(documents)
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None, chunker_type: str = None) -> List[Document]:
        """Chunk text using specified chunker"""
        chunker_type = chunker_type or self.default_chunker
        
        if chunker_type not in self.chunkers:
            raise ValueError(f"Unknown chunker type: {chunker_type}")
        
        chunker = self.chunkers[chunker_type]
        return chunker.chunk_text(text, metadata)
    
    def get_available_chunkers(self) -> List[str]:
        """Get list of available chunkers"""
        return list(self.chunkers.keys())

# Global instance
text_chunker_manager = TextChunkerManager() 