# CLAUDE.md

**Note**: This project uses [bd (beads)](https://github.com/steveyegge/beads) for issue tracking. Use `bd` commands instead of markdown TODOs. See AGENTS.md for workflow details.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mochi Donut is a spaced repetition learning integration system that converts content from various sources into high-quality flashcards following Andy Matuschak's principles. The system features an API-first architecture with multi-agent AI processing and integrates with Mochi for flashcard review.

## Architecture

### Core Stack
- **Backend**: FastAPI with async SQLAlchemy 2.0
- **AI Framework**: Claude Agent SDK (previously LangChain/LangGraph - migration complete)
- **AI Models**: Claude 3.5 (Haiku/Sonnet/Opus) with cost-optimized selection
- **Vector Database**: Chroma (local for dev, Chroma Cloud for production)
- **Task Queue**: Celery + Redis for background processing
- **Frontend**: Jinja2 + HTMX + Tailwind CSS (server-side rendering with progressive enhancement)
- **Deployment**: Docker on Fly.io with auto-scaling
- **Monitoring**: Dual strategy - Logfire + Prometheus

### Multi-Agent Architecture

The system uses Claude Agent SDK with specialized subagents:

1. **Content Processor Service**: Main orchestrator using Claude SDK (`ContentProcessorService`)
2. **Content Analyzer Subagent**: Extracts key concepts using Claude Haiku
3. **Prompt Generator Subagent**: Creates prompts following Matuschak's principles using Claude Sonnet
4. **Quality Reviewer Subagent**: Validates prompts against quality criteria using Claude Opus
5. **Refinement Subagent**: Iteratively improves prompts based on feedback using Claude Sonnet

**Migration Status**: ✅ LangChain/LangGraph migration complete (Step 8)
- Legacy agents removed: `base.py`, `orchestrator.py`, `content_analyzer.py`, `prompt_generator.py`, `quality_reviewer.py`, `refinement_agent.py`
- New implementation: `src/app/services/content_processor.py` + `src/app/agents/subagents.py`
- Legacy tasks deprecated: `src/app/tasks/agent_tasks.py` (use `ContentProcessorService` instead)

### Key Directories (Once Created)
```
src/
├── app/
│   ├── main.py           # FastAPI application
│   ├── db/               # Database models and config
│   ├── schemas/          # Pydantic models
│   ├── routers/          # API endpoints
│   ├── services/         # Business logic
│   ├── repositories/     # Data access layer
│   ├── agents/           # AI agents
│   └── tasks/            # Celery tasks
tests/                     # Test suite
```

## Development Commands

### Project Setup (When Implemented)
```bash
# Initialize project with uv
uv init
uv add fastapi sqlalchemy pydantic langchain chromadb celery redis

# Install dependencies
uv pip install -e .
```

### Development Server (Future)
```bash
# Run FastAPI server
uv run python -m app.main

# Run with auto-reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Operations (Future)
```bash
# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"

# Rollback migration
alembic downgrade -1
```

### Testing (Future)
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test
uv run pytest tests/test_endpoints.py::test_health_check
```

### Background Tasks (Future)
```bash
# Start Celery worker
uv run celery -A app.tasks worker --loglevel=info

# Start Celery beat scheduler
uv run celery -A app.tasks beat --loglevel=info
```

### Docker Operations (Future)
```bash
# Build and run with docker-compose
docker-compose up --build

# Run specific service
docker-compose up redis chroma

# View logs
docker-compose logs -f app
```

### Deployment (Future)
```bash
# Deploy to Fly.io
fly deploy

# View production logs
fly logs

# SSH into production
fly ssh console
```

## AI Developer Workflows (ADWs)

ADWs provide a programmatic interface for orchestrating Claude Code agents to plan, implement, test, and deploy features for Mochi Donut. This infrastructure enables reproducible development workflows with structured observability.

### Two-Layer Architecture

ADWs create a two-layer architecture:

1. **Agentic Layer** (`adws/`, `.claude/`, `specs/`) - Templates for engineering patterns, teaches agents how to operate
2. **Application Layer** (`src/app/`, `tests/`) - The actual Mochi Donut application code

The agentic layer wraps the application layer, providing programmatic AI-driven development capabilities.

### Usage Modes

**Mode A: Claude Max Subscription (Recommended for Development)**
- No API key configuration needed
- Works with your Claude Max subscription
- Perfect for interactive development
- Default mode - just start using ADWs!

**Mode B: API-Based (For CI/CD & Automation)**
- Requires `ANTHROPIC_API_KEY` in environment
- For headless workflows, CI/CD pipelines, webhooks
- See `adws/.env.sample` for configuration

### Essential Commands

**Adhoc Prompts:**
```bash
# Execute any prompt programmatically
./adws/adw_prompt.py "Analyze the LangChain agent implementation"
./adws/adw_prompt.py "Optimize Chroma vector search queries" --model opus

# Get help
./adws/adw_prompt.py --help
```

**Slash Commands:**
```bash
# Execute slash command templates
./adws/adw_slash_command.py /chore <id> "add error handling to Mochi integration"
./adws/adw_slash_command.py /implement specs/chore-<id>-*.md
./adws/adw_slash_command.py /prime  # Load project context

# Use different models
./adws/adw_slash_command.py /feature <id> "batch processing" --model opus
```

**Compound Workflows:**
```bash
# Plan + Implement in one command
./adws/adw_chore_implement.py "Add Redis caching to agent responses"

# TDD Planning - Break large tasks into agent-sized chunks
./adws/adw_plan_tdd.py "Implement OAuth2 authentication for Mochi API"
./adws/adw_plan_tdd.py specs/feature-auth.md --spec-file

# Output: specs/plans/plan-{id}.md with task breakdown
```

### Available Slash Commands

**Minimal Phase (Core):**
- `/chore` - Create plans for small tasks and fixes
- `/implement` - Execute implementation plans

**Enhanced Phase (Current Setup):**
- `/feature` - Create comprehensive feature plans
- `/plan-tdd` - Break down large specs into TDD tasks
- `/prime` - Load Mochi Donut context into agent memory

### Workflow Examples

**Example 1: Quick Fix**
```bash
# Plan and implement a small fix
./adws/adw_chore_implement.py "Fix GPT-5 model selection logic in agents"

# Or do it step-by-step
ID=$(uuidgen | cut -c1-8)
./adws/adw_slash_command.py /chore $ID "fix model selection"
./adws/adw_slash_command.py /implement specs/chore-$ID-*.md
```

**Example 2: Large Feature Development**
```bash
# 1. Break down the feature into tasks
./adws/adw_plan_tdd.py "Add batch content processing with progress tracking"

# 2. Review the generated plan
cat specs/plans/plan-*.md

# 3. Implement each task from the plan
# (Tasks are sized for optimal agent execution: Size S/M/L)
```

**Example 3: Context Loading**
```bash
# Prime Claude with Mochi Donut architecture before complex tasks
./adws/adw_slash_command.py /prime

# Then perform the complex task
./adws/adw_prompt.py "Design a new agent for quality scoring" --model opus
```

### Observability

All ADW executions create structured output in `agents/{adw_id}/{agent_name}/`:

```
agents/
└── abc12345/               # Unique ADW execution ID
    ├── planner/            # Planning phase
    │   ├── cc_raw_output.jsonl           # Raw JSONL stream
    │   ├── cc_raw_output.json            # Parsed messages
    │   ├── cc_final_object.json          # Final result
    │   ├── custom_summary_output.json    # High-level summary
    │   └── prompts/                      # Saved prompts
    └── builder/            # Implementation phase
        └── ...             # Same structure
```

This structured observability enables:
- Debugging failed workflows
- Analyzing agent behavior
- Reproducing execution results
- Cost tracking per execution

### Current Phase: Enhanced

You have the **Enhanced Phase** setup with:
- ✅ Core subprocess execution (`agent.py`)
- ✅ CLI wrappers (`adw_prompt.py`, `adw_slash_command.py`)
- ✅ Compound workflows (`adw_chore_implement.py`)
- ✅ TDD planning (`adw_plan_tdd.py`)
- ✅ Rich slash command templates

### Future: Scaled Phase with Beads Integration

When ready for production-scale workflows, upgrade to **Scaled Phase** for:
- **Beads Integration**: Local SQLite-based issue tracking (offline-first)
- **Git Worktree Isolation**: Safe parallel workflow execution
- **State Management**: Track workflow progress across phases
- **GitHub Integration**: Automated issue and PR management
- **Workflow Composition**: Complex multi-phase SDLC workflows

Beads support is planned for when you want to:
- Work offline without GitHub dependency
- Track ADW tasks locally in SQLite
- Have faster issue operations
- Maintain local development flow

### ADW Architecture Documentation

For detailed implementation notes, patterns, and extension guides, see:
- `adws/adw_modules/agent.py` - Core execution engine
- `.claude/commands/*.md` - Slash command templates
- `specs/plans/README.md` - TDD planning documentation

### Cost Optimization with ADWs

ADWs support model selection for cost optimization:
- **Haiku** (`--model haiku`): Fast, economical for simple tasks (~$0.25/1M input)
- **Sonnet** (default): Balanced for most workflows (~$3/1M input)
- **Opus** (`--model opus`): Maximum capability for complex planning (~$15/1M input)

Match model to task complexity for optimal cost/quality ratio.

## API Endpoints (Planned)

### Content Processing
- `POST /api/process/url` - Process web content via JinaAI
- `POST /api/process/pdf` - Convert PDF to markdown
- `POST /api/process/batch` - Batch processing

### Prompt Management
- `GET /api/prompts/{id}` - Retrieve specific prompt
- `PUT /api/prompts/{id}` - Edit prompt
- `POST /api/prompts/batch-review` - Review multiple prompts

### Mochi Integration
- `POST /api/mochi/cards/create` - Create Mochi cards
- `GET /api/mochi/decks` - List available decks

## Implementation Status

The project has a detailed 30-step implementation plan with GitHub issues (#1-#30). Currently in planning phase with the following structure:

- **Phase 0**: Foundation (Steps 1-6) - Project setup and basic API
- **Phase 1**: Content Processing (Steps 7-10) - JinaAI and Chroma integration
- **Phase 2**: AI Agents (Steps 11-15) - Multi-agent system
- **Phase 3**: Mochi Integration (Steps 16-17) - Card creation
- **Phase 4**: Web Interface (Step 18) - Review UI
- **Phase 5**: Infrastructure (Steps 19-22) - Celery, Redis, Docker
- **Phase 6**: Production (Steps 23-30) - Testing, monitoring, deployment

## Cost Optimization Strategy

### AI Model Selection
- **GPT-5 Nano** ($0.05/1M input): Simple extraction, classification
- **GPT-5 Mini** ($0.25/1M input): Standard prompt generation
- **GPT-5 Standard** ($1.25/1M input): Complex analysis, quality review
- Use caching (90% discount) for recently processed content

### Infrastructure Costs
- **Fly.io**: ~$7-10/month (small instance + storage)
- **Chroma Cloud**: ~$8-15/month (5GB storage)
- **Total estimate**: $30-70/month for production

## Quality Principles

Following Andy Matuschak's prompt writing principles:
- Prompts should be focused and specific
- Ensure precise, unambiguous language
- Maintain appropriate cognitive load
- Enable meaningful retrieval practice
- Prefer understanding over memorization

## Current Tasks

Track implementation progress in `todo.md` and GitHub issues. Each step builds incrementally without orphaned code. The project uses TDD where appropriate and maintains comprehensive test coverage.

## External Resources

- [Implementation Plan](./plan.md)
- [Product Specification](./spec.md)
- [GitHub Issues](https://github.com/JoshuaOliphant/mochi_donut/issues)
- [Andy Matuschak's Prompt Guide](https://andymatuschak.org/prompts/)
- [Mochi API Documentation](https://mochi.cards/docs/api)
- [JinaAI Reader API](https://jina.ai/reader)