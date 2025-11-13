# External Service Integrations

This directory contains client implementations for external services used by Mochi Donut:

## Available Integrations

### 1. JinaAI Reader API (`jina_client.py`)
- **Purpose**: Web content and PDF extraction
- **Features**:
  - Web page to markdown conversion
  - PDF content extraction
  - Intelligent caching (24-hour TTL)
  - Rate limiting for free tier
  - Comprehensive error handling

**Example Usage**:
```python
from app.integrations.jina_client import JinaAIClient

client = JinaAIClient()

# Extract web content
result = await client.extract_from_url("https://example.com")
print(f"Title: {result.title}")
print(f"Content: {result.content[:200]}...")

# Extract PDF content
pdf_result = await client.extract_from_pdf("https://example.com/document.pdf")
```

### 2. Chroma Vector Database (`chroma_client.py`)
- **Purpose**: Semantic search and content embeddings
- **Features**:
  - Collection management
  - Semantic similarity search
  - Duplicate detection using vector similarity
  - OpenAI embedding integration
  - Both local and cloud deployment support

**Example Usage**:
```python
from app.integrations.chroma_client import ChromaClient

client = ChromaClient()

# Create collection and add document
await client.get_or_create_collection("my_collection")
await client.add_document(
    collection_name="my_collection",
    document_id="doc1",
    content="This is some content",
    metadata={"source": "web"}
)

# Search for similar content
results = await client.search_similar(
    collection_name="my_collection",
    query_text="content search query",
    n_results=10
)
```

### 3. Mochi API (`mochi_client.py`)
- **Purpose**: Flashcard creation and management
- **Features**:
  - Single and batch card creation
  - Deck organization
  - Template support
  - Rate limiting and retry logic
  - Comprehensive error handling

**Example Usage**:
```python
from app.integrations.mochi_client import MochiClient, MochiCard

client = MochiClient()

# Create a single card
result = await client.create_card(
    content="What is the capital of France?",
    answer="Paris",
    deck_id="deck_123"
)

# Create multiple cards in batch
cards = [
    MochiCard(content="Question 1", answer="Answer 1"),
    MochiCard(content="Question 2", answer="Answer 2")
]
batch_result = await client.create_cards_batch(cards)
```

## Configuration

Add the following environment variables to your `.env` file:

```bash
# JinaAI Configuration
JINA_API_KEY=your_jina_api_key_here

# Chroma Configuration
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_API_KEY=your_chroma_api_key_here  # For cloud deployment

# Mochi Configuration
MOCHI_API_KEY=your_mochi_api_key_here

# OpenAI (for embeddings)
OPENAI_API_KEY=your_openai_api_key_here
```

## Service Integration

The integration clients are used by higher-level services:

- **ContentProcessorService**: Uses JinaAI for content extraction and Chroma for storage
- **SearchService**: Uses Chroma for semantic search capabilities
- **PromptService**: Uses Mochi for flashcard creation and management

## Dependency Injection

Use the dependency injection helpers for proper singleton management:

```python
from app.integrations.dependencies import (
    get_jina_client,
    get_chroma_client,
    get_mochi_client,
    health_check_integrations
)

# Get singleton instances
jina = get_jina_client()
chroma = get_chroma_client()
mochi = get_mochi_client()

# Check health of all services
health_status = await health_check_integrations()
```

## Error Handling

All clients implement comprehensive error handling:

- **JinaAIError**: Base exception for JinaAI operations
- **ChromaError**: Base exception for Chroma operations
- **MochiError**: Base exception for Mochi operations

Specific exceptions include rate limiting, authentication, and connection errors.

## Rate Limiting

- **JinaAI**: 1 second delay between requests for free tier
- **Mochi**: 0.5 second delay between requests
- **Chroma**: No built-in rate limiting

## Caching

- **JinaAI**: 24-hour content cache with automatic expiration
- **Chroma**: Native vector similarity caching
- **Mochi**: No caching (real-time operations)

## Production Considerations

1. **API Keys**: Store securely and rotate regularly
2. **Rate Limits**: Monitor usage and upgrade plans as needed
3. **Error Monitoring**: Implement alerts for service failures
4. **Backup**: Regularly backup Chroma collections
5. **Scaling**: Use Chroma Cloud for production workloads

## Health Monitoring

Use the built-in health check endpoints:

```python
# Check individual service health
jina_healthy = True  # JinaAI doesn't have a health endpoint
chroma_healthy = await chroma_client.health_check()
mochi_healthy = await mochi_client.health_check()

# Check all services
health_status = await health_check_integrations()
```