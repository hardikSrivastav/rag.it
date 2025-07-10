# RAG System Backend

Internal RAG (Retrieval-Augmented Generation) System / Personal Knowledge Lake - A powerful backend service for ingesting, indexing, and querying documents using vector search and LLM generation.

## 🚀 Features

- **Multi-format Document Support**: PDF, DOCX, TXT, MD files
- **Vector Search**: Powered by Qdrant vector database
- **Local Embeddings**: Using sentence-transformers models
- **Dual LLM Support**: AWS Bedrock (primary) with OpenAI fallback
- **Streaming Responses**: Real-time chat interface
- **RESTful API**: Comprehensive API for all operations
- **Docker Ready**: Complete containerization with docker-compose
- **Comprehensive Logging**: Structured logging with file persistence

## 🏗 Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   File Upload   │    │   Text Chunking  │    │   Embeddings    │
│                 │───▶│                  │───▶│                 │
│ PDF/DOCX/TXT/MD │    │ LangChain Split  │    │ Sentence-Trans  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Chat Query    │    │   RAG Pipeline   │    │ Vector Storage  │
│                 │───▶│                  │◀───│                 │
│ Streaming API   │    │ Retrieve + Gen   │    │ Qdrant Database │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌──────────────────┐
                       │  LLM Providers   │
                       │                  │
                       │ AWS Bedrock +    │
                       │ OpenAI Fallback  │
                       └──────────────────┘
```

## 🛠 Quick Start

### Prerequisites

- Docker and Docker Compose
- At least 4GB RAM available
- AWS credentials (optional, for Bedrock)
- OpenAI API key (optional, for fallback)

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd rag-system

# Create environment file
cp backend/.env.example backend/.env
```

### 2. Configure Environment

Edit `backend/.env` with your settings:

```env
# Required - will use local defaults if not set
ENVIRONMENT=development

# Optional - for AWS Bedrock (primary LLM)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1

# Optional - for OpenAI (fallback LLM)
OPENAI_API_KEY=your_openai_api_key

# Embedding model (will download automatically)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### 3. Launch Services

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f rag-backend

# Check health
curl http://localhost:8792/health
```

### 4. First Document Upload

```bash
# Upload a document
curl -X POST "http://localhost:8792/api/v1/ingest/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your-document.pdf" \
  -F "source_tool=manual_upload"

# Check processing status
curl "http://localhost:8792/api/v1/ingest/status/1"
```

### 5. Query the System

```bash
# Send a query
curl -X POST "http://localhost:8792/api/v1/chat/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?", "top_k": 5}'

# Streaming query (for real-time responses)
curl -X POST "http://localhost:8792/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarize the key points", "top_k": 5}'
```

## 📡 API Endpoints

### File Ingestion

- `POST /api/v1/ingest/upload` - Upload and process files
- `POST /api/v1/ingest/push` - Ingest text data from other tools
- `GET /api/v1/ingest/status/{id}` - Check processing status
- `DELETE /api/v1/ingest/document/{id}` - Delete document

### Chat & Query

- `POST /api/v1/chat/query` - Send query, get complete response
- `POST /api/v1/chat/stream` - Send query, get streaming response
- `GET /api/v1/chat/sessions` - List chat sessions
- `GET /api/v1/chat/sessions/{id}/history` - Get chat history

### Document Management

- `GET /api/v1/documents/` - List all documents
- `GET /api/v1/documents/{id}` - Get document details
- `GET /api/v1/documents/stats/summary` - Get statistics

### Health & Monitoring

- `GET /api/v1/health/` - Basic health check
- `GET /api/v1/health/detailed` - Detailed system health
- `GET /api/v1/health/components/vector-store` - Vector DB health
- `GET /api/v1/health/components/llm-providers` - LLM health

## 🔧 Configuration

### Embedding Models

The system uses local sentence-transformers models. Popular options:

- `sentence-transformers/all-MiniLM-L6-v2` (384 dim, fast)
- `sentence-transformers/all-mpnet-base-v2` (768 dim, better quality)
- `sentence-transformers/all-MiniLM-L12-v2` (384 dim, balanced)

### LLM Providers

1. **AWS Bedrock** (Primary)
   - Claude 3 Sonnet (default)
   - Claude 3 Haiku (faster)
   - Requires AWS credentials

2. **OpenAI** (Fallback)
   - GPT-4 Turbo (default)
   - GPT-3.5 Turbo (cheaper)
   - Requires API key

### Text Chunking

- **Chunk Size**: 1000 characters (default)
- **Overlap**: 200 characters (default)
- **Strategy**: Recursive character splitting

## 🐳 Docker Services

The system runs these services:

- **rag-backend**: FastAPI application (port 8792)
- **qdrant**: Vector database (port 6338)

### Service Ports

- Backend API: `http://localhost:8792`
- Qdrant UI: `http://localhost:6338/dashboard`
- API Docs: `http://localhost:8792/docs`

## 📁 Data Storage

- **Uploaded Files**: `./uploads/` (local filesystem)
- **Vector Data**: `./qdrant_data/` (Qdrant storage)
- **Metadata DB**: `./data/rag_system.db` (SQLite)
- **Logs**: `./logs/` (structured JSON logs)

## 🔍 Monitoring

### Log Files

Logs are stored in `./logs/rag_system_YYYYMMDD.log` with structured JSON format:

```json
{
  "timestamp": "2024-01-01T12:00:00.000Z",
  "level": "info",
  "logger": "rag_system",
  "message": "Document processed successfully",
  "document_id": 1,
  "chunks": 15
}
```

### Health Checks

```bash
# Basic health
curl http://localhost:8792/api/v1/health/

# Detailed health with all components
curl http://localhost:8792/api/v1/health/detailed

# Vector database health
curl http://localhost:8792/api/v1/health/components/vector-store
```

## 🚀 Development

### Local Development

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run locally (requires running Qdrant)
uvicorn app.main:app --host 0.0.0.0 --port 8792 --reload
```

### Environment Variables

See `backend/.env.example` for all available configuration options.

### Adding New Document Types

1. Create loader in `app/services/loaders.py`
2. Add file extension to `ALLOWED_EXTENSIONS` in config
3. Update content type mapping

### Custom Integrations

Use the `/api/v1/ingest/push` endpoint to send data from other tools:

```python
import requests

data = {
    "source_tool": "my_custom_tool",
    "content": "Document text content...",
    "metadata": {
        "custom_field": "value",
        "importance": "high"
    }
}

response = requests.post(
    "http://localhost:8792/api/v1/ingest/push",
    json=data
)
```

## 🔒 Security Notes

- No authentication required (internal use)
- Files stored locally (ensure proper permissions)
- API keys in environment variables only
- Consider VPN/firewall for production

## 📝 License

Internal use only.

## 🆘 Support

For issues:
1. Check logs in `./logs/`
2. Verify health endpoints
3. Check Docker container status
4. Review environment configuration 