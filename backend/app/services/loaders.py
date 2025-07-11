from typing import List, Dict, Any, Optional
from pathlib import Path
import os
from abc import ABC, abstractmethod

from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredMarkdownLoader,
    TextLoader
)
from langchain_core.documents import Document

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

class PythonDocumentLoader(BaseDocumentLoader):
    """Python source file loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load Python document"""
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "python",
                    "loader": "TextLoader",
                    "language": "python"
                })
            
            logger.info("Python file loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load Python file", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() == ".py"

class JavaScriptDocumentLoader(BaseDocumentLoader):
    """JavaScript source file loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load JavaScript document"""
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "javascript",
                    "loader": "TextLoader",
                    "language": "javascript"
                })
            
            logger.info("JavaScript file loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load JavaScript file", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() == ".js"

class TypeScriptDocumentLoader(BaseDocumentLoader):
    """TypeScript source file loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load TypeScript document"""
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "typescript",
                    "loader": "TextLoader",
                    "language": "typescript"
                })
            
            logger.info("TypeScript file loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load TypeScript file", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() == ".ts"

class JSONDocumentLoader(BaseDocumentLoader):
    """JSON document loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load JSON document"""
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "json",
                    "loader": "TextLoader",
                    "language": "json"
                })
            
            logger.info("JSON file loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load JSON file", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() == ".json"

class TSXDocumentLoader(BaseDocumentLoader):
    """TSX (TypeScript React) document loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load TSX document"""
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "tsx",
                    "loader": "TextLoader",
                    "language": "tsx"
                })
            
            logger.info("TSX file loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load TSX file", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() == ".tsx"

class JSXDocumentLoader(BaseDocumentLoader):
    """JSX (JavaScript React) document loader"""
    
    def load(self, file_path: str) -> List[Document]:
        """Load JSX document"""
        try:
            loader = TextLoader(file_path, encoding="utf-8")
            documents = loader.load()
            
            # Add metadata
            for doc in documents:
                doc.metadata.update({
                    "source": file_path,
                    "file_type": "jsx",
                    "loader": "TextLoader",
                    "language": "jsx"
                })
            
            logger.info("JSX file loaded successfully", 
                       file_path=file_path, 
                       documents=len(documents))
            return documents
            
        except Exception as e:
            logger.error("Failed to load JSX file", file_path=file_path, error=str(e))
            raise
    
    def supports_file_type(self, file_extension: str) -> bool:
        return file_extension.lower() == ".jsx"

class DocumentLoaderManager:
    """Manager for different document loaders"""
    
    def __init__(self):
        self.loaders = [
            PDFDocumentLoader(),
            WordDocumentLoader(),
            MarkdownDocumentLoader(),
            TextDocumentLoader(),
            PythonDocumentLoader(),
            JavaScriptDocumentLoader(),
            TypeScriptDocumentLoader(),
            JSONDocumentLoader(),
            TSXDocumentLoader(),
            JSXDocumentLoader()
        ]
    
    def _is_file_empty_or_whitespace(self, file_path: str) -> bool:
        """Check if file is empty or contains only whitespace"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return True
            
            # Check file size first
            if file_path_obj.stat().st_size == 0:
                logger.warning("File is empty", file_path=file_path, size=0)
                return True
            
            # For small files, check if content is only whitespace
            if file_path_obj.stat().st_size < 1000:  # Only check small files to avoid loading large files
                try:
                    with open(file_path_obj, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if not content.strip():
                            logger.warning("File contains only whitespace", 
                                         file_path=file_path, 
                                         size=file_path_obj.stat().st_size)
                            return True
                except Exception as e:
                    logger.debug("Could not check file content for whitespace", 
                               file_path=file_path, error=str(e))
            
            return False
            
        except Exception as e:
            logger.error("Error checking if file is empty", file_path=file_path, error=str(e))
            return False
    
    def load_document(self, file_path: str) -> List[Document]:
        """Load document using appropriate loader"""
        file_extension = Path(file_path).suffix
        
        # Check if file is empty or contains only whitespace
        if self._is_file_empty_or_whitespace(file_path):
            raise ValueError(f"File is empty or contains only whitespace: {file_path}")
        
        # Find appropriate loader
        for loader in self.loaders:
            if loader.supports_file_type(file_extension):
                logger.info("Loading document", 
                           file_path=file_path, 
                           loader=loader.__class__.__name__)
                
                # Load document and validate content
                documents = loader.load(file_path)
                
                # Filter out empty documents
                valid_documents = []
                for doc in documents:
                    if doc.page_content and doc.page_content.strip():
                        valid_documents.append(doc)
                    else:
                        logger.warning("Skipping empty document chunk", 
                                     file_path=file_path,
                                     chunk_content_length=len(doc.page_content) if doc.page_content else 0)
                
                if not valid_documents:
                    raise ValueError(f"No valid content found in file after loading: {file_path}")
                
                return valid_documents
        
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
            elif isinstance(loader, PythonDocumentLoader):
                extensions.append(".py")
            elif isinstance(loader, JavaScriptDocumentLoader):
                extensions.append(".js")
            elif isinstance(loader, TypeScriptDocumentLoader):
                extensions.append(".ts")
            elif isinstance(loader, JSONDocumentLoader):
                extensions.append(".json")
            elif isinstance(loader, TSXDocumentLoader):
                extensions.append(".tsx")
            elif isinstance(loader, JSXDocumentLoader):
                extensions.append(".jsx")
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