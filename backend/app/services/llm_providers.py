from typing import List, Dict, Any, Optional, Iterator, AsyncIterator, Union
from abc import ABC, abstractmethod
import asyncio
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import openai
from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class BaseLLMProvider(ABC):
    """Base class for LLM providers"""
    
    @abstractmethod
    async def generate_response(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate a response from the LLM"""
        pass
    
    @abstractmethod
    async def generate_streaming_response(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> AsyncIterator[str]:
        """Generate a streaming response from the LLM"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available"""
        pass

class AWSBedrockProvider(BaseLLMProvider):
    """AWS Bedrock LLM provider"""
    
    def __init__(self):
        self.client = None
        self.model_id = settings.BEDROCK_MODEL_ID
        self.region = settings.AWS_REGION
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize AWS Bedrock client"""
        try:
            # Create boto3 session
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                session = boto3.Session(
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=self.region
                )
            else:
                # Use default credentials (IAM role, environment variables, etc.)
                session = boto3.Session(region_name=self.region)
            
            # Create Bedrock client
            self.client = session.client('bedrock-runtime', region_name=self.region)
            
            logger.info("AWS Bedrock client initialized", 
                       model_id=self.model_id,
                       region=self.region)
            
        except Exception as e:
            logger.error("Failed to initialize AWS Bedrock client", error=str(e))
            self.client = None
    
    def _build_messages(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Build messages for Claude 3 models"""
        messages = []
        
        # Add user message first (required by AWS Bedrock)
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        })
        
        if context:
            # Add assistant message with context
            context_text = "\n\n".join([
                f"Source: {doc.get('metadata', {}).get('source', 'Unknown')}\n{doc.get('text', '')}"
                for doc in context
            ])
            
            context_message = f"""You are a helpful assistant. Use the following context to answer questions. If the answer is not in the context, please say so.

Context:
{context_text}"""
            
            messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": context_message}]
            })
            
            # Add another user message to ask the actual question
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            })
        
        return messages
    
    async def generate_response(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate a response from AWS Bedrock"""
        if not self.client:
            raise Exception("AWS Bedrock client not available")
        
        try:
            messages = self._build_messages(prompt, context)
            
            # Prepare request body (Claude 3 Messages format)
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": settings.MAX_TOKENS,
                "temperature": settings.TEMPERATURE,
                "messages": messages
            }
            
            # Make request
            response = self.client.invoke_model(
                body=json.dumps(body),
                modelId=self.model_id,
                accept="application/json",
                contentType="application/json"
            )
            
            # Parse response
            response_body = json.loads(response.get('body').read())
            content = response_body.get('content', [])
            
            # Extract text from response content
            response_text = ""
            for block in content:
                if block.get('type') == 'text':
                    response_text += block.get('text', '')
            
            logger.info("Generated response with AWS Bedrock", 
                       prompt_length=len(prompt),
                       response_length=len(response_text))
            
            return response_text.strip()
            
        except Exception as e:
            logger.error("Failed to generate response with AWS Bedrock", error=str(e))
            raise
    
    async def generate_streaming_response(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> AsyncIterator[str]:
        """Generate a streaming response from AWS Bedrock"""
        if not self.client:
            raise Exception("AWS Bedrock client not available")
        
        try:
            messages = self._build_messages(prompt, context)
            
            # Prepare request body (Claude 3 Messages format)
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": settings.MAX_TOKENS,
                "temperature": settings.TEMPERATURE,
                "messages": messages
            }
            
            # Make streaming request
            response = self.client.invoke_model_with_response_stream(
                body=json.dumps(body),
                modelId=self.model_id,
                accept="application/json",
                contentType="application/json"
            )
            
            # Process streaming response
            for event in response.get('body'):
                chunk = json.loads(event['chunk']['bytes'])
                if 'content' in chunk:
                    for block in chunk['content']:
                        if block.get('type') == 'text':
                            yield block.get('text', '')
                    
        except Exception as e:
            logger.error("Failed to generate streaming response with AWS Bedrock", error=str(e))
            raise
    
    def is_available(self) -> bool:
        """Check if AWS Bedrock is available"""
        if not self.client:
            return False
        
        try:
            # Test with a simple request
            messages = [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}]
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 10,
                "temperature": 0.1,
                "messages": messages
            }
            
            response = self.client.invoke_model(
                body=json.dumps(body),
                modelId=self.model_id,
                accept="application/json",
                contentType="application/json"
            )
            
            return True
            
        except Exception as e:
            logger.error("AWS Bedrock availability check failed", error=str(e))
            return False

class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider"""
    
    def __init__(self):
        self.client = None
        self.model = settings.OPENAI_MODEL
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        try:
            if not settings.OPENAI_API_KEY:
                logger.warning("OpenAI API key not provided")
                return
            
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            logger.info("OpenAI client initialized", model=self.model)
            
        except Exception as e:
            logger.error("Failed to initialize OpenAI client", error=str(e))
            self.client = None
    
    def _build_messages(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, str]]:
        """Build messages for OpenAI chat completion"""
        messages = []
        
        if context:
            # Add system message with context
            context_text = "\n\n".join([
                f"Source: {doc.get('metadata', {}).get('source', 'Unknown')}\n{doc.get('text', '')}"
                for doc in context
            ])
            
            system_message = f"""You are a helpful assistant. Use the following context to answer questions. If the answer is not in the context, please say so.

Context:
{context_text}"""
            
            messages.append({"role": "system", "content": system_message})
        
        # Add user message
        messages.append({"role": "user", "content": prompt})
        
        return messages
    
    async def generate_response(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate a response from OpenAI"""
        if not self.client:
            raise Exception("OpenAI client not available")
        
        try:
            messages = self._build_messages(prompt, context)
            
            # Make request
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE
            )
            
            completion = response.choices[0].message.content
            
            logger.info("Generated response with OpenAI", 
                       prompt_length=len(prompt),
                       response_length=len(completion))
            
            return completion
            
        except Exception as e:
            logger.error("Failed to generate response with OpenAI", error=str(e))
            raise
    
    async def generate_streaming_response(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> AsyncIterator[str]:
        """Generate a streaming response from OpenAI"""
        if not self.client:
            raise Exception("OpenAI client not available")
        
        try:
            messages = self._build_messages(prompt, context)
            
            # Make streaming request
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE,
                stream=True
            )
            
            # Process streaming response
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error("Failed to generate streaming response with OpenAI", error=str(e))
            raise
    
    def is_available(self) -> bool:
        """Check if OpenAI is available"""
        if not self.client:
            return False
        
        try:
            # Test with a simple request
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10,
                temperature=0.1
            )
            
            return True
            
        except Exception as e:
            logger.error("OpenAI availability check failed", error=str(e))
            return False

class LLMManager:
    """Manager for different LLM providers with fallback logic"""
    
    def __init__(self):
        self.providers = {
            "bedrock": AWSBedrockProvider(),
            "openai": OpenAIProvider()
        }
        self.provider_order = ["bedrock", "openai"]  # Primary to fallback
    
    def _get_available_provider(self) -> Optional[BaseLLMProvider]:
        """Get the first available provider"""
        for provider_name in self.provider_order:
            provider = self.providers[provider_name]
            if provider.is_available():
                logger.info("Using provider", provider=provider_name)
                return provider
        
        logger.error("No LLM providers available")
        return None
    
    async def generate_response(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate a response using the first available provider"""
        provider = self._get_available_provider()
        if not provider:
            raise Exception("No LLM providers available")
        
        return await provider.generate_response(prompt, context)
    
    async def generate_streaming_response(self, prompt: str, context: Optional[List[Dict[str, Any]]] = None) -> AsyncIterator[str]:
        """Generate a streaming response using the first available provider"""
        provider = self._get_available_provider()
        if not provider:
            raise Exception("No LLM providers available")
        
        async for chunk in provider.generate_streaming_response(prompt, context):
            yield chunk
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return [name for name, provider in self.providers.items() if provider.is_available()]
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all providers"""
        return {name: provider.is_available() for name, provider in self.providers.items()}

# Global instance
llm_manager = LLMManager() 