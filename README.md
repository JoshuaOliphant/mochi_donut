# Mochi Donut

Spaced repetition learning integration system powered by Claude Agent SDK.

## Overview

Mochi Donut converts content from various sources (web articles, PDFs, podcasts) into high-quality flashcards following Andy Matuschak's principles for effective spaced repetition learning. The system uses Claude Agent SDK's multi-agent architecture to intelligently generate, review, and refine flashcard prompts.

## Architecture

**AI Framework**: Claude Agent SDK with specialized subagents
- **Content Analyzer**: Extracts key concepts and assesses complexity
- **Prompt Generator**: Creates diverse flashcard types
- **Quality Reviewer**: Evaluates prompts against Matuschak's principles
- **Refinement Agent**: Iteratively improves low-quality prompts

**Backend**: FastAPI with async SQLAlchemy 2.0
**Vector Database**: Chroma for semantic search
**Task Queue**: Celery + Redis for background processing
**Frontend**: Jinja2 + HTMX + Tailwind CSS

## Quick Start

### Prerequisites

- Python 3.11+
- uv (for dependency management)
- Redis (for Celery)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd mochi_donut

# Copy environment template
cp .env.sample .env

# Edit .env with your API keys
# - ANTHROPIC_API_KEY: Your Claude API key
# - MOCHI_API_KEY: Your Mochi API key

# Install dependencies
uv sync

# Initialize database
uv run alembic upgrade head
```

### Running the Application

```bash
# Start the development server
uv run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start Celery worker
uv run celery -A src.app.tasks.celery_app worker --loglevel=info
```

## Development

See [CLAUDE.md](./CLAUDE.md) for detailed development guidelines and workflow.

### Issue Tracking

This project uses [bd (beads)](https://github.com/steveyegge/beads) for issue tracking. See [AGENTS.md](./AGENTS.md) for workflow details.

```bash
# Check ready work
bd ready

# Claim an issue
bd update <issue-id> --status in_progress

# Complete work
bd close <issue-id> --reason "Completed"
```

## Project Status

Currently implementing Phase 0: Foundation with Claude Agent SDK migration.

-  Step 1: Project initialization
- ó Step 2: Database models
- ó Step 3: FastAPI skeleton
- ó Step 4: Pydantic schemas

See planning documents in `history/` for detailed implementation plans.

## License

MIT
