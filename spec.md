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
- **Database**: PostgreSQL with pgvector for embeddings
- **Storage**: Content storage with full-text search
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

Using PydanticAI evals module:
- **LLM-as-judge** evaluating against Matuschak's principles
- Performance tracking from Mochi review sessions
- Continuous improvement through feedback loops
- A/B testing of prompt generation strategies

## Feature Roadmap

### Phase 1: MVP (Week 1-2)
**Goal**: Process single URL, review prompts, send to Mochi

Features:
- Web scraping for articles
- Basic prompt generation with Claude/GPT-5
- Web interface for prompt review/editing
- Mochi API integration
- Basic content storage

Success Criteria:
- Can process a blog post
- Generate 5-10 quality prompts
- Successfully create Mochi cards

### Phase 2: Raindrop Integration (Week 3)
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

### Phase 3: Notion Integration (Week 4)
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

### Phase 4: Multi-Format Support (Week 5-6)
**Goal**: Expand content source types

Features:
- PDF processing (uploaded and URL)
- YouTube transcript extraction
- Markdown file support
- Format-specific prompt strategies

Success Criteria:
- Process technical PDF documentation
- Extract video key points
- Handle various content densities

### Phase 5: Automation & Intelligence (Week 7-8)
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
POST /api/process/url
POST /api/process/pdf
POST /api/process/text
POST /api/process/batch

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
```

### Data Models

```python
# Core Models
Content:
  - id: UUID
  - source_url: str
  - source_type: Enum[web, pdf, youtube, notion, raindrop]
  - raw_text: str
  - processed_text: str
  - embedding: vector
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
```

### Technology Stack

- **Backend**: FastAPI, SQLAlchemy 2.0, Pydantic
- **AI**: PydanticAI, Claude 3 Opus/GPT-5
- **Database**: PostgreSQL with pgvector
- **Cache**: Redis
- **Task Queue**: Celery + Redis
- **Deployment**: Docker on Fly.io
- **Monitoring**: Logfire + Prometheus
- **Testing**: pytest with PydanticAI evals

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

- **AI Costs**: ~$50-100/month for API calls (personal use)
- **Infrastructure**: Fly.io ~$20-50/month
- **Database**: Included in Fly.io or separate managed instance
- **Mochi**: Existing subscription

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

## Next Steps

1. Set up development environment
2. Create GitHub repository
3. Implement Phase 1 MVP
4. Deploy to Fly.io staging
5. Begin daily usage and iteration

---

*This specification is a living document and will be updated as the system evolves based on usage and feedback.*