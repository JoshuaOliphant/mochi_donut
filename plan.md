# Mochi Donut - Implementation Plan

## Project Overview
Building a spaced repetition learning integration system that converts content from various sources into high-quality flashcards following Andy Matuschak's principles. The system is API-first, integrates with Mochi, and uses a multi-agent architecture for intelligent content processing.

## Architecture Summary
- **Backend**: FastAPI with async SQLAlchemy
- **AI**: Multi-agent system using LangGraph and GPT-5 models
- **Vector DB**: Chroma for semantic search
- **Deployment**: Fly.io with Docker
- **Monitoring**: Logfire + Prometheus

## Implementation Phases

### Phase 0: Foundation (Prerequisites)
Small, safe steps to establish the project structure and basic infrastructure.

### Phase 1: Core API & Database
Build the minimal FastAPI application with database models and basic endpoints.

### Phase 2: Content Processing Pipeline
Implement markdown conversion and basic content storage.

### Phase 3: AI Agent System
Build the multi-agent architecture for prompt generation.

### Phase 4: Mochi Integration
Connect to Mochi API for card creation.

### Phase 5: Web Interface
Create the review and editing interface.

### Phase 6: Production Readiness
Add monitoring, testing, and deployment configuration.

---

## Detailed Implementation Steps

### **Step 1: Project Initialization**
Create the basic project structure with dependency management.

**GitHub Issue Title**: Initialize project with uv and basic structure

```text
Set up the initial Python project using uv for dependency management. Create the basic directory structure including src/, tests/, and configuration files. Initialize git repository and create .gitignore with Python defaults. Set up pre-commit hooks for code quality.

Tasks:
- Initialize uv project with pyproject.toml
- Create directory structure (src/app, tests, docs)
- Configure .gitignore for Python/FastAPI
- Add .env.example with placeholder variables
- Create initial README with project description
```

---

### **Step 2: FastAPI Application Skeleton**
Set up the minimal FastAPI application with health check endpoint.

**GitHub Issue Title**: Create minimal FastAPI application with health endpoint

```text
Create the basic FastAPI application structure with a simple health check endpoint. This establishes the foundation for all future API development. Configure CORS, basic middleware, and application factory pattern.

Tasks:
- Create src/app/main.py with FastAPI app
- Add health check endpoint at /api/health
- Configure basic CORS middleware
- Set up application factory pattern
- Add basic logging configuration
- Create simple test for health endpoint
```

---

### **Step 3: Database Models and Configuration**
Set up SQLAlchemy with async support and create core data models.

**GitHub Issue Title**: Configure SQLAlchemy and create core data models

```text
Set up SQLAlchemy 2.0 with async support using SQLite for development. Create the core data models for Content and Prompt entities. Configure Alembic for database migrations.

Tasks:
- Install SQLAlchemy and asyncpg dependencies
- Create database configuration in src/app/db/
- Define Content model with required fields
- Define Prompt model with relationships
- Set up Alembic for migrations
- Create initial migration
- Add database connection to FastAPI lifespan
```

---

### **Step 4: Pydantic Schemas and Validation**
Create Pydantic models for request/response validation.

**GitHub Issue Title**: Add Pydantic schemas for API validation

```text
Create comprehensive Pydantic schemas for all API endpoints. Ensure proper validation, serialization, and documentation generation.

Tasks:
- Create schemas/content.py with ContentCreate, ContentResponse
- Create schemas/prompt.py with PromptCreate, PromptUpdate, PromptResponse
- Add validation rules and examples
- Configure schema settings for JSON serialization
- Add schema tests with valid/invalid data
```

---

### **Step 5: Content Repository Pattern**
Implement repository pattern for database operations.

**GitHub Issue Title**: Implement repository pattern for Content operations

```text
Create repository classes to abstract database operations. This provides a clean separation between business logic and data access.

Tasks:
- Create repositories/base.py with BaseRepository
- Implement ContentRepository with CRUD operations
- Add pagination support
- Implement duplicate detection logic
- Create unit tests for repository methods
- Add dependency injection to FastAPI
```

---

### **Step 6: Basic Content Processing Endpoint**
Create the first functional endpoint for URL processing.

**GitHub Issue Title**: Add POST /api/process/url endpoint

```text
Implement the basic URL processing endpoint that accepts a URL and stores it in the database. For now, just store the URL and metadata without actual content extraction.

Tasks:
- Create routers/content.py
- Implement POST /api/process/url endpoint
- Add URL validation
- Store content record in database
- Return content ID and status
- Add integration test for endpoint
```

---

### **Step 7: JinaAI Integration for Web Scraping**
Integrate JinaAI Reader API for markdown conversion.

**GitHub Issue Title**: Integrate JinaAI Reader API for web-to-markdown conversion

```text
Add JinaAI Reader API integration to convert web content to markdown. Handle rate limiting and errors gracefully.

Tasks:
- Create services/jina_reader.py
- Implement fetch_as_markdown function
- Add retry logic with exponential backoff
- Handle API errors and rate limits
- Update content processing to use JinaAI
- Add mock for testing
- Store markdown content in database
```

---

### **Step 8: Chroma Vector Store Setup**
Initialize Chroma for vector storage and semantic search.

**GitHub Issue Title**: Set up Chroma vector database for content storage

```text
Configure Chroma vector database for local development. Create collections and implement basic storage operations.

Tasks:
- Install chromadb dependency
- Create services/vector_store.py
- Initialize Chroma client and collection
- Implement add_document function
- Add embedding generation for content
- Create search_similar function
- Test vector operations
```

---

### **Step 9: Simple Prompt Generation**
Create basic prompt generation without AI.

**GitHub Issue Title**: Implement simple rule-based prompt generation

```text
Create a simple prompt generator that creates basic Q&A pairs from content. This will be replaced with AI later but provides immediate value.

Tasks:
- Create services/prompt_generator.py
- Implement extract_key_sentences function
- Generate simple Q&A pairs from headers
- Create factual prompts from lists
- Store prompts in database
- Link prompts to content
- Add tests for generation logic
```

---

### **Step 10: Prompt Management Endpoints**
Add CRUD endpoints for prompt management.

**GitHub Issue Title**: Add prompt management endpoints (GET, PUT, DELETE)

```text
Implement endpoints for retrieving, updating, and deleting prompts. This allows users to review and edit generated prompts.

Tasks:
- Create routers/prompts.py
- Implement GET /api/prompts/{id}
- Add PUT /api/prompts/{id} for editing
- Add DELETE /api/prompts/{id}
- Implement GET /api/prompts/by-content/{content_id}
- Add pagination to prompt lists
- Create integration tests
```

---

### **Step 11: LangChain and Agent Framework Setup**
Set up LangChain with basic agent structure.

**GitHub Issue Title**: Configure LangChain and create agent base classes

```text
Install and configure LangChain with LangGraph for agent orchestration. Create base classes for agents without AI integration yet.

Tasks:
- Install langchain and langgraph
- Create agents/base.py with BaseAgent class
- Set up agent state management
- Create agents/orchestrator.py skeleton
- Implement basic message passing
- Add agent configuration loader
- Test agent initialization
```

---

### **Step 12: Content Analysis Agent**
Implement the first AI agent for content analysis.

**GitHub Issue Title**: Create Content Analysis Agent with GPT-5 integration

```text
Build the Content Analysis Agent that extracts key concepts and structure from markdown content. Use GPT-5-nano for efficiency.

Tasks:
- Create agents/content_analyzer.py
- Integrate OpenAI client with GPT-5-nano
- Implement analyze_content method
- Extract key concepts and topics
- Identify content complexity
- Determine prompt density recommendations
- Add structured output parsing
- Create tests with mocked responses
```

---

### **Step 13: Prompt Generation Agent**
Build the AI-powered prompt generator.

**GitHub Issue Title**: Implement Prompt Generation Agent following Matuschak's principles

```text
Create the Prompt Generation Agent that creates high-quality prompts based on Matuschak's principles. Use GPT-5-mini for balanced cost/quality.

Tasks:
- Create agents/prompt_generator.py
- Implement generation for different prompt types
- Add Matuschak's principles as system prompt
- Generate factual, conceptual, and procedural prompts
- Implement cloze deletion generation
- Ensure variety and appropriate difficulty
- Add batch generation support
- Test with various content types
```

---

### **Step 14: Quality Review Agent**
Add quality assurance for generated prompts.

**GitHub Issue Title**: Build Quality Review Agent for prompt validation

```text
Implement the Quality Review Agent that evaluates prompts against quality criteria. Use GPT-5-standard for thorough analysis.

Tasks:
- Create agents/quality_reviewer.py
- Define quality criteria checklist
- Implement prompt evaluation logic
- Score prompts on multiple dimensions
- Flag low-quality prompts
- Suggest improvements
- Add LangChain evaluators
- Create quality metrics tracking
```

---

### **Step 15: Agent Orchestration**
Connect agents into a cohesive workflow.

**GitHub Issue Title**: Implement orchestrator for multi-agent workflow

```text
Build the orchestrator that manages the workflow between all agents. Handle errors, retries, and state management.

Tasks:
- Complete agents/orchestrator.py
- Implement workflow state machine
- Add error handling and retries
- Create agent communication protocol
- Implement feedback loops
- Add workflow monitoring
- Test complete pipeline
- Add performance metrics
```

---

### **Step 16: Mochi API Client**
Create integration with Mochi API.

**GitHub Issue Title**: Build Mochi API client for card management

```text
Implement the Mochi API client for creating cards and managing decks. Handle authentication and API limits.

Tasks:
- Create services/mochi_client.py
- Implement authentication
- Add get_decks function
- Create create_card function
- Implement batch card creation
- Handle API errors and retries
- Add configuration for API keys
- Mock Mochi API for testing
```

---

### **Step 17: Card Creation Endpoint**
Connect prompt approval to Mochi card creation.

**GitHub Issue Title**: Add endpoint for creating Mochi cards from prompts

```text
Create endpoint that sends approved prompts to Mochi as flashcards. Handle batching and deck selection.

Tasks:
- Add POST /api/mochi/cards/create endpoint
- Implement single card creation
- Add POST /api/mochi/cards/batch for bulk
- Link prompts to Mochi card IDs
- Add deck selection logic
- Handle creation failures
- Update prompt status after creation
- Add integration tests
```

---

### **Step 18: Basic Web Interface**
Create minimal web UI for prompt review.

**GitHub Issue Title**: Build basic web interface with Jinja2 and HTMX

```text
Create a simple web interface for reviewing and editing prompts before sending to Mochi. Use server-side rendering with progressive enhancement.

Tasks:
- Set up Jinja2 templates
- Create base template with Tailwind CSS
- Add prompt review page
- Implement inline editing with HTMX
- Add approve/reject buttons
- Create batch operations UI
- Style with Tailwind utilities
- Test without JavaScript
```

---

### **Step 19: Background Task Processing**
Add Celery for async processing.

**GitHub Issue Title**: Configure Celery with Redis for background tasks

```text
Set up Celery for handling long-running tasks like batch content processing. Use Redis as the message broker.

Tasks:
- Install Celery and Redis dependencies
- Configure Celery app
- Create tasks/content_tasks.py
- Implement async content processing task
- Add task status tracking
- Create task monitoring endpoint
- Test with Redis container
- Add retry logic for failed tasks
```

---

### **Step 20: Redis Caching Layer**
Implement caching for performance.

**GitHub Issue Title**: Add Redis caching for API responses

```text
Implement Redis caching to improve performance for frequently accessed data. Cache processed content and generated prompts.

Tasks:
- Create services/cache.py
- Implement cache decorators
- Add caching to content endpoints
- Cache Mochi deck lists
- Implement cache invalidation
- Add cache metrics
- Configure TTL strategies
- Test cache hit/miss scenarios
```

---

### **Step 21: Duplicate Detection System**
Implement intelligent duplicate detection.

**GitHub Issue Title**: Build duplicate detection with URL hash and semantic similarity

```text
Create a system to detect duplicate content using both URL hashing and semantic similarity via Chroma.

Tasks:
- Add URL normalization and hashing
- Implement semantic similarity search
- Create duplicate detection service
- Add similarity threshold configuration
- Handle near-duplicates
- Create duplicate management UI
- Add deduplication statistics
- Test with various content types
```

---

### **Step 22: Docker Configuration**
Create Docker setup for local development.

**GitHub Issue Title**: Add Docker and docker-compose configuration

```text
Create Dockerfile and docker-compose setup for consistent development environment. Include all services.

Tasks:
- Create multi-stage Dockerfile
- Add docker-compose.yml
- Configure service networking
- Add volume mounts for development
- Create .dockerignore
- Add health checks
- Document Docker commands
- Test complete stack startup
```

---

### **Step 23: Testing Suite**
Comprehensive test coverage setup.

**GitHub Issue Title**: Implement comprehensive test suite with pytest

```text
Set up pytest with fixtures, mocks, and coverage reporting. Ensure all critical paths are tested.

Tasks:
- Configure pytest and coverage
- Create test fixtures for database
- Add API client fixture
- Mock external services
- Write unit tests for services
- Add integration tests for endpoints
- Create end-to-end test scenarios
- Set up GitHub Actions for CI
```

---

### **Step 24: Monitoring and Observability**
Add Logfire and metrics collection.

**GitHub Issue Title**: Configure Logfire monitoring and Prometheus metrics

```text
Implement comprehensive monitoring with Logfire for application insights and Prometheus for metrics.

Tasks:
- Install and configure Logfire
- Add structured logging
- Create custom metrics
- Implement trace correlation
- Add performance monitoring
- Configure error tracking
- Create monitoring dashboards
- Set up alerts for critical issues
```

---

### **Step 25: Fly.io Deployment**
Deploy to production on Fly.io.

**GitHub Issue Title**: Configure and deploy to Fly.io

```text
Set up Fly.io deployment with auto-scaling and persistent storage. Configure production environment.

Tasks:
- Create fly.toml configuration
- Set up secrets management
- Configure persistent volumes
- Add production database
- Set up Chroma Cloud
- Configure auto-scaling rules
- Add deployment GitHub Action
- Test production deployment
```

---

### **Step 26: Error Handling and Recovery**
Robust error handling throughout the system.

**GitHub Issue Title**: Implement comprehensive error handling and recovery

```text
Add proper error handling, fallback mechanisms, and recovery strategies throughout the application.

Tasks:
- Create custom exception classes
- Add global exception handlers
- Implement circuit breakers
- Add fallback for AI failures
- Create error recovery workflows
- Add user-friendly error messages
- Implement retry strategies
- Test failure scenarios
```

---

### **Step 27: API Documentation**
Generate and customize API documentation.

**GitHub Issue Title**: Create comprehensive API documentation with examples

```text
Generate OpenAPI documentation and create developer-friendly API docs with examples and guides.

Tasks:
- Configure FastAPI OpenAPI generation
- Add detailed endpoint descriptions
- Create request/response examples
- Write API usage guide
- Add authentication documentation
- Create Postman collection
- Set up API versioning
- Deploy docs to /api/docs
```

---

### **Step 28: Performance Optimization**
Optimize for speed and efficiency.

**GitHub Issue Title**: Optimize application performance and response times

```text
Profile and optimize the application for better performance. Focus on database queries and AI operations.

Tasks:
- Add query optimization
- Implement connection pooling
- Optimize prompt generation
- Add response compression
- Implement lazy loading
- Optimize Docker image size
- Add CDN for static assets
- Benchmark and document improvements
```

---

### **Step 29: Security Hardening**
Implement security best practices.

**GitHub Issue Title**: Implement security hardening and best practices

```text
Add security measures including rate limiting, input sanitization, and authentication improvements.

Tasks:
- Add rate limiting middleware
- Implement input sanitization
- Add CSRF protection
- Configure security headers
- Implement API key rotation
- Add audit logging
- Run security scanner
- Fix identified vulnerabilities
```

---

### **Step 30: Final Integration and Polish**
Complete integration testing and UI polish.

**GitHub Issue Title**: Final integration testing and UI improvements

```text
Complete final integration testing, UI improvements, and prepare for launch. Ensure everything works smoothly together.

Tasks:
- Run full integration test suite
- Polish UI with loading states
- Add success notifications
- Implement keyboard shortcuts
- Add user preferences
- Create onboarding flow
- Write user documentation
- Prepare launch announcement
```

---

## Success Criteria for MVP (Phase 1)
- [ ] Can process a single URL and extract content
- [ ] Generates 5-10 quality prompts per article
- [ ] Allows manual review and editing of prompts
- [ ] Successfully creates cards in Mochi
- [ ] Basic duplicate detection works
- [ ] System is deployable to Fly.io
- [ ] Monitoring shows system health

## Next Steps After MVP
1. Raindrop.io integration for bulk processing
2. Notion integration for podcast highlights
3. PDF and YouTube support
4. Advanced automation features
5. Knowledge graph visualization