# Spaced Repetition Learning Integration - Product Specification

## Executive Summary

An API-first service that converts various content sources (web articles, PDFs, YouTube videos, etc.) into high-quality spaced repetition flashcards following Andy Matuschak's principles. Initially integrates with Mochi for the review interface, with potential for a standalone interface in the future.

## Core Philosophy

Based on Andy Matuschak's approach to spaced repetition prompts:
- Create genuine understanding, not just memorization
- Focus on retrieval practice and active learning
- Generate focused, precise, and tractable prompts
- Emphasize quality over quantity while covering all important concepts

## Target User

Primary: Technical professional who consumes both technical documentation and casual learning content
Secondary: Other learners who want to retain knowledge from diverse digital sources

## System Architecture

### API-First Design
- **Core**: Python/FastAPI backend
- **Deployment**: Fly.io with auto-scaling
- **Vector Database**: Chroma (local for dev, Chroma Cloud for production)
- **Storage**: Content storage with semantic search and full-text search
- **Monitoring**: Dual strategy - Fly.io Prometheus + Logfire

### Multi-Agent AI Architecture

Following Anthropic's agent patterns, using **Orchestrator-Workers** with **Evaluator-Optimizer**:

1. **Orchestrator Agent**
   - Routes content to appropriate processing pipeline
   - Manages workflow between agents
   - Handles error recovery and retries

2. **Content Analysis Agent**
   - Extracts key concepts and structure
   - Identifies content type and complexity
   - Determines appropriate prompt density

3. **Prompt Generation Agent**
   - Creates prompts following Matuschak's principles
   - Generates multiple prompt types:
     - Factual prompts
     - Procedural prompts
     - Conceptual prompts
     - Open list prompts
     - Cloze deletions

4. **Quality Review Agent**
   - Evaluates prompts against quality criteria:
     - Focused and specific
     - Precise and unambiguous
     - Consistent answers expected
     - Appropriate difficulty
     - Meaningful retrieval practice

5. **Refinement Agent**
   - Iteratively improves prompts based on feedback
   - Ensures variety and coverage
   - Adapts to user preferences over time

### Quality Assurance System

Using LangChain evaluation framework:
- **LLM-as-judge** pattern for evaluating prompts against Matuschak's principles:
  - Focused and specific targeting
  - Clear and precise language
  - Appropriate cognitive load
  - Meaningful retrieval practice
- **LangChain Components**:
  - Custom evaluators for prompt quality scoring
  - Chain-based evaluation pipelines
  - Feedback integration with LangSmith (optional)
- Performance tracking from Mochi review sessions
- Continuous improvement through feedback loops
- Simple evaluation process optimized for single-user feedback

## Feature Roadmap

### Phase 1: MVP
**Goal**: Process single URL, review prompts, send to Mochi

Features:
- Web content conversion to markdown via JinaAI API
- Basic prompt generation with GPT-5 models
- Web interface for prompt review/editing
- Mochi API integration
- Chroma vector storage for content

Success Criteria:
- Can process a blog post
- Generate 5-10 quality prompts
- Successfully create Mochi cards

### Phase 2: Raindrop Integration
**Goal**: Bulk process bookmarked content

Features:
- Raindrop.io API integration
- Bookmark sync and selection interface
- Batch processing queue
- Duplicate detection (URL hash + semantic similarity)

Success Criteria:
- Process 10 bookmarks in one session
- Detect and skip duplicates
- Organize into appropriate decks

### Phase 3: Notion Integration
**Goal**: Process Snipd podcast highlights

Features:
- Notion API integration
- Database query for Snipd snippets
- Audio transcript processing
- Context preservation from highlights

Success Criteria:
- Extract and process podcast insights
- Maintain source attribution
- Generate contextual prompts

### Phase 4: Multi-Format Support
**Goal**: Expand content source types

Features:
- PDF processing (uploaded and URL) with conversion to markdown
- YouTube transcript extraction and markdown conversion
- Native markdown file support
- Format-specific prompt strategies with unified markdown pipeline

Success Criteria:
- Process technical PDF documentation
- Extract video key points
- Handle various content densities

### Phase 5: Automation & Intelligence
**Goal**: Background processing with high confidence

Features:
- Quality metrics and confidence scoring
- Auto-processing for high-confidence content
- Learning from user edits
- Personal preference adaptation
- Template library for common patterns

Success Criteria:
- 80% of prompts need no editing
- Background processing option enabled
- Measurable quality improvement

### Future Phases
- Knowledge graph visualization
- Semantic search across all content
- Custom review interface (Mochi alternative)
- Mobile app
- Team sharing features

## Technical Specifications

### API Endpoints

```python
# Content Processing
POST /api/process/url          # Uses JinaAI for web-to-markdown
POST /api/process/pdf          # Converts PDF to markdown
POST /api/process/text         # Direct markdown processing
POST /api/process/batch        # Batch markdown conversion

# Integration Management
GET  /api/sources/raindrop/sync
POST /api/sources/raindrop/process
GET  /api/sources/notion/databases
POST /api/sources/notion/process

# Prompt Management
GET  /api/prompts/{id}
PUT  /api/prompts/{id}
POST /api/prompts/batch-review
POST /api/prompts/approve

# Mochi Integration
GET  /api/mochi/decks
POST /api/mochi/cards/create
POST /api/mochi/cards/batch

# Quality & Analytics
GET  /api/analytics/performance
POST /api/feedback/prompt/{id}
GET  /api/templates

# Vector Search
POST /api/search/semantic      # Chroma-powered semantic search
GET  /api/search/similar/{content_id}
```

### Data Models

```python
# Core Models
Content:
  - id: UUID
  - source_url: str
  - source_type: Enum[web, pdf, youtube, notion, raindrop]
  - raw_text: str
  - markdown_content: str      # Unified markdown format
  - chroma_id: str            # Reference to Chroma vector store
  - metadata: JSON
  - created_at: datetime
  - hash: str

Prompt:
  - id: UUID
  - content_id: UUID
  - question: str
  - answer: str
  - prompt_type: Enum
  - confidence_score: float
  - version: int
  - mochi_card_id: str (optional)
  - created_at: datetime
  - edited_at: datetime

QualityMetric:
  - prompt_id: UUID
  - metric_type: str
  - score: float
  - feedback: JSON
  - created_at: datetime

ChromaDocument:
  - collection_name: str
  - document_id: str
  - content_id: UUID         # Link back to Content model
  - metadata: JSON
```

### Technology Stack

- **Backend**: FastAPI, SQLAlchemy 2.0, Pydantic
- **AI Framework**: LangChain with native Chroma integration
  - `langchain-chroma` package for vector store operations
  - LangGraph for agent orchestration and state management
  - Built-in evaluation framework for quality assurance
- **AI Models**: GPT-5 family with tiered usage:
  - GPT-5 Nano ($0.05/1M input): Simple extraction, classification
  - GPT-5 Mini ($0.25/1M input): Standard prompt generation
  - GPT-5 Standard ($1.25/1M input): Complex analysis, quality review
- **Vector Database**: Chroma
  - Local development: Free open-source instance
  - Production: Chroma Cloud with persistent collections
  - Semantic search with embeddings
  - Collection forking for versioning
- **Content Processing**:
  - JinaAI Reader API for web-to-markdown (rate-limited free tier)
  - ReaderLM-v2 for complex HTML structures
- **Cache**: Redis
- **Task Queue**: Celery + Redis
- **Deployment**: Docker on Fly.io
- **Monitoring**: Logfire + Prometheus
- **Testing**: pytest with LangChain evaluation tools

## Security & Privacy

- API authentication via JWT tokens
- Encrypted storage for sensitive content
- Rate limiting on all endpoints
- Audit logging for data access
- GDPR-compliant data handling
- Backup strategy with point-in-time recovery

## Success Metrics

### Primary KPIs
- Prompts requiring no edits: >70%
- Average processing time: <30s per article
- Retention improvement: >20% vs. passive reading
- Daily active usage rate

### Quality Metrics
- Prompt clarity score (via LLM judge)
- Answer consistency rating
- Concept coverage percentage
- User satisfaction (edit rate)

## Deployment Strategy

1. **Local Development**: Docker Compose environment
2. **Staging**: Fly.io staging app with test data
3. **Production**: Fly.io with automated backups
4. **CI/CD**: GitHub Actions for testing and deployment

## Budget Considerations

### Detailed Cost Breakdown (Based on 2025 Pricing)

#### AI Costs (OpenAI GPT-5 Family)
- **GPT-5 Nano**: $0.05/1M input tokens, $0.40/1M output tokens
- **GPT-5 Mini**: $0.25/1M input tokens, $2.00/1M output tokens
- **GPT-5 Standard**: $1.25/1M input tokens, $10.00/1M output tokens
- **Caching Discount**: 90% off for recently used input tokens
- **Estimated Monthly**: $15-30 (processing ~200 articles with smart model selection)

#### Chroma Vector Database
- **Development**: Free (local instance)
- **Production** (Chroma Cloud Starter):
  - $5 free credits to start
  - Writing: $2.50/GiB (one-time)
  - Storage: $0.33/GiB/month
  - Queries: $0.0075/TiB queried + $0.09/GiB returned
  - **Estimated Monthly**: $8-15 (for ~5GB storage and moderate queries)

#### Fly.io Infrastructure
- **Small FastAPI App** (shared-cpu-1x, 256MB): $1.94/month
- **Persistent Volume** (10GB): $1.50/month
- **Dedicated IPv4**: $2/month (optional)
- **Bandwidth**: ~$2-5/month (100GB free in US/EU)
- **Estimated Monthly**: $7-10

#### JinaAI Reader API
- **Free Tier**: 20 requests/minute without key, 200/minute with free key
- **Enhanced Model**: ReaderLM-v2 costs 3x tokens for complex content
- **Estimated Monthly**: $0-10 (likely free for personal use volume)

#### Total Monthly Costs
- **Development Phase**: ~$0 (all local/free tiers)
- **Production Minimal**: ~$30-40/month
- **Production Standard**: ~$50-70/month
- **Mochi**: Existing subscription (not included)

## Risk Mitigation

- **Content parsing failures**: Fallback to simpler extraction
- **AI quality issues**: Human review gate initially
- **API rate limits**: Queue management and retry logic
- **Data loss**: Regular backups and version history

## Development Principles

1. **Iterative**: Each phase produces usable functionality
2. **API-First**: All features available programmatically
3. **Quality-Focused**: Better fewer good prompts than many poor ones
4. **User-Controlled**: Always allow manual override
5. **Learning System**: Continuously improve from feedback
6. **Markdown-First**: Convert all content to markdown for consistent processing
7. **Cost-Optimized**: Use appropriate model sizes (GPT-5 nano to full) based on task complexity
8. **Vector-Native**: Leverage Chroma for semantic search and content discovery

## Next Steps

1. Set up development environment
2. Create GitHub repository
3. Implement Phase 1 MVP
4. Deploy to Fly.io staging
5. Begin daily usage and iteration

---

*This specification is a living document and will be updated as the system evolves based on usage and feedback.*