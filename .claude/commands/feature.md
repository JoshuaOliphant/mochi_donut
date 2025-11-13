# Feature Planning

Create a plan to implement the feature using the specified markdown `Plan Format`. Research the codebase and create a thorough plan.

## Variables
adw_id: $1
prompt: $2

## Instructions

- If the adw_id or prompt is not provided, stop and ask the user to provide them.
- Create a plan to implement the feature described in the `prompt`
- The plan should be comprehensive, well-designed, and follow existing patterns in Mochi Donut
- Create the plan in the `specs/` directory with filename: `feature-{adw_id}-{descriptive-name}.md`
  - Replace `{descriptive-name}` with a short, descriptive name based on the feature (e.g., "batch-processing", "real-time-sync", "quality-metrics")
- Research the codebase starting with `README.md` and `CLAUDE.md`
- Replace every <placeholder> in the `Plan Format` with the requested value
- Use your reasoning model: THINK HARD about the feature requirements, design, and implementation approach
- Follow existing patterns and conventions in the codebase
- Design for extensibility and maintainability

## Codebase Structure

**Mochi Donut** is a spaced repetition learning integration system using multi-agent AI architecture.

### Key Directories:
- `README.md` - Project overview and setup instructions (start here)
- `CLAUDE.md` - Development guidelines and architecture documentation
- `spec.md` - Product specification and requirements
- `src/app/` - Main application code
  - `main.py` - FastAPI application entry point
  - `agents/` - Multi-agent AI system (LangChain/LangGraph) for content processing
  - `api/v1/endpoints/` - REST API endpoint handlers
  - `db/models.py` - Database models (SQLAlchemy 2.0 async)
  - `schemas/` - Pydantic data models for validation
  - `services/` - Business logic layer
  - `repositories/` - Data access layer (repository pattern)
  - `integrations/` - External API clients (JinaAI, Chroma, Mochi)
  - `tasks/` - Celery background tasks for async processing
  - `web/` - HTMX + Jinja2 web interface for flashcard review
- `tests/` - Test suite (pytest with async support)
- `alembic/` - Database migration scripts
- `adws/` - AI Developer Workflow scripts
- `specs/` - Specification and plan documents

### Tech Stack:
- **Backend**: FastAPI (async), SQLAlchemy 2.0 (async), Python 3.11+
- **AI Framework**: LangChain + LangGraph for multi-agent orchestration
- **AI Models**: GPT-5 family (Nano/Mini/Standard) with cost-optimized selection
- **Vector DB**: Chroma (local dev, Chroma Cloud production)
- **Task Queue**: Celery + Redis for background processing
- **Frontend**: Jinja2 + HTMX + Tailwind CSS (progressive enhancement, no JavaScript frameworks)
- **Package Manager**: uv

## Plan Format

```md
# Feature: <feature name>

## Metadata
adw_id: `{adw_id}`
prompt: `{prompt}`

## Feature Description
<describe the feature in detail, including its purpose and value to users>

## User Story
As a <type of user>
I want to <action/goal>
So that <benefit/value>

## Problem Statement
<clearly define the specific problem or opportunity this feature addresses>

## Solution Statement
<describe the proposed solution approach and how it solves the problem>

## Relevant Files
Use these files to implement the feature:

<list files relevant to the feature with bullet points explaining why. Include new files to be created under an h3 'New Files' section if needed>

## Implementation Plan
### Phase 1: Foundation
<describe the foundational work needed before implementing the main feature>

### Phase 2: Core Implementation
<describe the main implementation work for the feature>

### Phase 3: Integration
<describe how the feature will integrate with existing functionality>

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

<list step by step tasks as h3 headers with bullet points. Start with foundational changes then move to specific changes. Include creating tests throughout the implementation process>

### 1. <First Task Name>
- <specific action>
- <specific action>

### 2. <Second Task Name>
- <specific action>
- <specific action>

<continue with additional tasks as needed>

## Testing Strategy
### Unit Tests
<describe unit tests needed for the feature>

### Integration Tests
<describe integration tests needed>

### Edge Cases
<list edge cases that need to be tested>

## Acceptance Criteria
<list specific, measurable criteria that must be met for the feature to be considered complete>

## Validation Commands
Execute these commands to validate the feature is complete:

<list specific commands to validate the work. Be precise about what to run>
- Example: `uv run pytest tests/unit/test_agents.py` - Test agent functionality
- Example: `uv run pytest tests/integration/` - Run integration tests
- Example: `uv run ruff check src/` - Check code style


## Notes
<optional additional context, future considerations, or dependencies. If new libraries are needed, specify using `uv add`>
```

## Feature
Use the feature description from the `prompt` variable.

## Report

Return the path to the plan file created.
