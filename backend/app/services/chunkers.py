from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import hashlib

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter
)
from langchain_core.documents import Document

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
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Chunk text into smaller pieces"""
        pass

class RecursiveCharacterChunker(BaseTextChunker):
    """Recursive character text chunker - good for most documents"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        logger.info("Initialized RecursiveCharacterChunker", 
                   chunk_size=chunk_size, 
                   chunk_overlap=chunk_overlap)
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk documents using recursive character splitting"""
        try:
            chunks = self.text_splitter.split_documents(documents)
            
            # Add chunk metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "chunk_id": i,
                    "chunker": "RecursiveCharacterChunker",
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap
                })
            
            logger.info("Documents chunked successfully", 
                       original_docs=len(documents), 
                       chunks=len(chunks))
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk documents", error=str(e))
            raise
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Chunk text using recursive character splitting"""
        try:
            if metadata is None:
                metadata = {}
            
            # Create document from text
            document = Document(page_content=text, metadata=metadata)
            
            # Chunk the document
            chunks = self.chunk_documents([document])
            
            logger.info("Text chunked successfully", 
                       text_length=len(text), 
                       chunks=len(chunks))
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk text", error=str(e))
            raise

class CharacterChunker(BaseTextChunker):
    """Simple character text chunker"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, separator: str = "\n\n"):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
        self.text_splitter = CharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator=separator
        )
        
        logger.info("Initialized CharacterChunker", 
                   chunk_size=chunk_size, 
                   chunk_overlap=chunk_overlap,
                   separator=separator)
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk documents using character splitting"""
        try:
            chunks = self.text_splitter.split_documents(documents)
            
            # Add chunk metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "chunk_id": i,
                    "chunker": "CharacterChunker",
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                    "separator": self.separator
                })
            
            logger.info("Documents chunked successfully", 
                       original_docs=len(documents), 
                       chunks=len(chunks))
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk documents", error=str(e))
            raise
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Chunk text using character splitting"""
        try:
            if metadata is None:
                metadata = {}
            
            # Create document from text
            document = Document(page_content=text, metadata=metadata)
            
            # Chunk the document
            chunks = self.chunk_documents([document])
            
            logger.info("Text chunked successfully", 
                       text_length=len(text), 
                       chunks=len(chunks))
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk text", error=str(e))
            raise

class TokenChunker(BaseTextChunker):
    """Token-based text chunker"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        logger.info("Initialized TokenChunker", 
                   chunk_size=chunk_size, 
                   chunk_overlap=chunk_overlap)
    
    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk documents using token splitting"""
        try:
            chunks = self.text_splitter.split_documents(documents)
            
            # Add chunk metadata
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "chunk_id": i,
                    "chunker": "TokenChunker",
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap
                })
            
            logger.info("Documents chunked successfully", 
                       original_docs=len(documents), 
                       chunks=len(chunks))
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk documents", error=str(e))
            raise
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Chunk text using token splitting"""
        try:
            if metadata is None:
                metadata = {}
            
            # Create document from text
            document = Document(page_content=text, metadata=metadata)
            
            # Chunk the document
            chunks = self.chunk_documents([document])
            
            logger.info("Text chunked successfully", 
                       text_length=len(text), 
                       chunks=len(chunks))
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk text", error=str(e))
            raise

class ChunkerManager:
    """Manager for different text chunkers"""
    
    def __init__(self):
        self.chunkers = {
            "recursive": RecursiveCharacterChunker(),
            "character": CharacterChunker(),
            "token": TokenChunker()
        }
        self.default_chunker = "recursive"
        
        logger.info("Initialized ChunkerManager", 
                   available_chunkers=list(self.chunkers.keys()),
                   default_chunker=self.default_chunker)
    
    def get_chunker(self, chunker_type: Optional[str] = None) -> BaseTextChunker:
        """Get chunker by type"""
        if chunker_type is None:
            chunker_type = self.default_chunker
        
        if chunker_type not in self.chunkers:
            logger.warning("Unknown chunker type, using default", 
                          requested_type=chunker_type,
                          default_type=self.default_chunker)
            chunker_type = self.default_chunker
        
        return self.chunkers[chunker_type]
    
    def chunk_documents(self, documents: List[Document], chunker_type: Optional[str] = None) -> List[Document]:
        """Chunk documents using specified chunker"""
        chunker = self.get_chunker(chunker_type)
        return chunker.chunk_documents(documents)
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None, chunker_type: Optional[str] = None) -> List[Document]:
        """Chunk text using specified chunker"""
        chunker = self.get_chunker(chunker_type)
        return chunker.chunk_text(text, metadata)
    
    def get_available_chunkers(self) -> List[str]:
        """Get list of available chunker types"""
        return list(self.chunkers.keys())

# Global instance
chunker_manager = ChunkerManager() 