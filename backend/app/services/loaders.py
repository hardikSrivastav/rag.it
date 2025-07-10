from typing import List, Dict, Any, Optional
from pathlib import Path
import os
from abc import ABC, abstractmethod

from langchain.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredMarkdownLoader,
    TextLoader
)
from langchain.schema import Document

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class BaseDocumentLoader(ABC):
    """Base class for document loaders"""
    
    @abstractmethod
    def load(self, file_path: str) -> List[Document]:
        """Load document and return LangChain Document objects"""
        pass
    
    @abstractmethod
    def supports_file_type(self, file_extension: str) -> bool:
        """Check if this loader supports the given file extension"""
        pass

class PDFDocumentLoader(BaseDocumentLoader):
    """PDF document loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load PDF document"""
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "pdf",
                    "loader": "PyPDFLoader"
                })
            
            logger.info("PDF loaded successfully", 
                       file_path=file_path, 
                       pages=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load PDF", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() == ".pdf"

class WordDocumentLoader(BaseDocumentLoader):
    """Word document loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load Word document"""
        try:
            loader = UnstructuredWordDocumentLoader(file_path)
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "docx",
                    "loader": "UnstructuredWordDocumentLoader"
                })
            
            logger.info("Word document loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load Word document", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() in [".docx", ".doc"]

class MarkdownDocumentLoader(BaseDocumentLoader):
    """Markdown document loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load Markdown document"""
        try:
            loader = UnstructuredMarkdownLoader(file_path)
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "markdown",
                    "loader": "UnstructuredMarkdownLoader"
                })
            
            logger.info("Markdown document loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load Markdown document", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() in [".md", ".markdown"]

class TextDocumentLoader(BaseDocumentLoader):
    """Plain text document loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load text document"""
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "text",
                    "loader": "TextLoader"
                })
            
            logger.info("Text document loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load text document", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() == ".txt"

class DocumentLoaderManager:
    """Manager for different document loaders"""
    
    def __init__(self):
        self.loaders = [
            PDFDocumentLoader(),
            WordDocumentLoader(),
            MarkdownDocumentLoader(),
            TextDocumentLoader()
        ]
    
    def load_document(self, file_path: str) -> List[Document]:
        """Load document using appropriate loader"""
        file_extension = Path(file_path).suffix
        
        # Find appropriate loader
        for loader in self.loaders:
            if loader.supports_file_type(file_extension):
                logger.info("Loading document", 
                           file_path=file_path, 
                           loader=loader.__class__.__name__)
                return loader.load(file_path)
        
        # If no loader found, raise error
        raise ValueError(f"No loader found for file type: {file_extension}")
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions"""
        extensions = []
        for loader in self.loaders:
            if isinstance(loader, PDFDocumentLoader):
                extensions.append(".pdf")
            elif isinstance(loader, WordDocumentLoader):
                extensions.extend([".docx", ".doc"])
            elif isinstance(loader, MarkdownDocumentLoader):
                extensions.extend([".md", ".markdown"])
            elif isinstance(loader, TextDocumentLoader):
                extensions.append(".txt")
        return extensions
    
    def is_supported_file(self, file_path: str) -> bool:
        """Check if file is supported"""
        file_extension = Path(file_path).suffix
        return file_extension.lower() in self.get_supported_extensions()

class CustomDataLoader:
    """Loader for custom data pushed from other tools"""
    
    def load_from_text(self, text: str, metadata: Dict[str, Any]) -> Document:
        """Load document from text content"""
        try:
            document = Document(
                page_content=text,
                metadata={
                    "source": metadata.get("source", "custom_data"),
                    "source_tool": metadata.get("source_tool", "unknown"),
                    "file_type": "text",
                    "loader": "CustomDataLoader",
                    **metadata
                }
            )
            
            logger.info("Custom data loaded successfully", 
                       source_tool=metadata.get("source_tool", "unknown"),
                       text_length=len(text))
            return document
            
        except Exception as e:
            logger.error("Failed to load custom data", error=str(e))
            raise

# Global instances
document_loader_manager = DocumentLoaderManager()
custom_data_loader = CustomDataLoader() 