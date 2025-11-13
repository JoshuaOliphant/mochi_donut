# Chore Planning

Create a plan to complete the chore using the specified markdown `Plan Format`. Research the codebase and create a thorough plan.

## Variables
adw_id: $1
prompt: $2

## Instructions

- If the adw_id or prompt is not provided, stop and ask the user to provide them.
- Create a plan to complete the chore described in the `prompt`
- The plan should be simple, thorough, and precise
- Create the plan in the `specs/` directory with filename: `chore-{adw_id}-{descriptive-name}.md`
  - Replace `{descriptive-name}` with a short, descriptive name based on the chore (e.g., "update-readme", "add-logging", "refactor-agent")
- Research the codebase starting with `README.md` and `CLAUDE.md`
- Replace every <placeholder> in the `Plan Format` with the requested value

## Codebase Structure

**Mochi Donut** is a spaced repetition learning integration system that converts content into high-quality flashcards following Andy Matuschak's principles.

### Key Directories:
- `README.md` - Project overview and setup instructions (start here)
- `CLAUDE.md` - Development guidelines and architecture documentation
- `spec.md` - Product specification and requirements
- `src/app/` - Main application code
  - `main.py` - FastAPI application entry point
  - `agents/` - Multi-agent AI system (LangChain/LangGraph)
  - `api/v1/endpoints/` - API endpoint handlers
  - `db/` - Database models and configuration (SQLAlchemy async)
  - `schemas/` - Pydantic data models
  - `services/` - Business logic layer
  - `repositories/` - Data access layer
  - `integrations/` - External API clients (JinaAI, Chroma, Mochi)
  - `tasks/` - Celery background tasks
  - `web/` - HTMX + Jinja2 web interface
- `tests/` - Test suite (pytest with async support)
- `alembic/` - Database migration scripts
- `adws/` - AI Developer Workflow scripts
- `.claude/commands/` - Claude command templates
- `specs/` - Specification and plan documents

### Tech Stack:
- **Backend**: FastAPI (async), SQLAlchemy 2.0 (async), Python 3.11+
- **AI Framework**: LangChain + LangGraph for multi-agent orchestration
- **AI Models**: GPT-5 family (Nano/Mini/Standard) with cost optimization
- **Vector DB**: Chroma (local dev, Chroma Cloud production)
- **Task Queue**: Celery + Redis
- **Frontend**: Jinja2 + HTMX + Tailwind CSS (server-side rendering)
- **Package Manager**: uv

## Plan Format

```md
# Chore: <chore name>

## Metadata
adw_id: `{adw_id}`
prompt: `{prompt}`

## Chore Description
<describe the chore in detail based on the prompt>

## Relevant Files
Use these files to complete the chore:

<list files relevant to the chore with bullet points explaining why. Include new files to be created under an h3 'New Files' section if needed>

## Step by Step Tasks
IMPORTANT: Execute every step in order, top to bottom.

<list step by step tasks as h3 headers with bullet points. Start with foundational changes then move to specific changes. Last step should validate the work>

### 1. <First Task Name>
- <specific action>
- <specific action>

### 2. <Second Task Name>
- <specific action>
- <specific action>

## Validation Commands
Execute these commands to validate the chore is complete:

<list specific commands to validate the work. Be precise about what to run>
- Example: `uv run pytest tests/unit/test_agents.py` - Test agent functionality
- Example: `uv run python -m pytest tests/` - Run full test suite
- Example: `uv run ruff check src/` - Check code style

## Notes
<optional additional context or considerations>
```

## Chore
Use the chore description from the `prompt` variable.

## Report

Return the path to the plan file created.
