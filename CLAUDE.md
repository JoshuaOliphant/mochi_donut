# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mochi Donut is a minimal MCP server that converts web content into Mochi flashcards following Andy Matuschak's spaced repetition principles. Built with FastMCP and httpx - no database, no web framework, no background tasks.

## Architecture

```
src/mochi_donut/
├── __init__.py     # Package entry point, exports mcp and main
└── server.py       # Complete MCP server implementation
```

The server exposes:
- **Tools**: `fetch_url` (JinaAI Reader), `list_decks`, `create_cards` (Mochi API)
- **Resources**: `matuschak://principles`, `matuschak://examples`
- **Prompts**: `generate_flashcards`, `review_flashcards`

Core business logic lives in `_impl` functions (e.g., `_fetch_url_impl`) which are wrapped by `@mcp.tool` decorators. Test the `_impl` functions directly since decorators return `FunctionTool` objects.

## Development Commands

```bash
# Run the MCP server
uv run python -m mochi_donut.server

# Run all tests
uv run pytest

# Run specific test class
uv run pytest tests/test_server.py::TestFetchUrlTool -v

# Run single test
uv run pytest tests/test_server.py::TestFetchUrlTool::test_fetch_url_success -v
```

## Environment Variables

- `MOCHI_API_KEY` - Required. Get from https://app.mochi.cards/settings/api

## Installing in Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "mochi-donut": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mochi_donut", "python", "-m", "mochi_donut.server"],
      "env": {"MOCHI_API_KEY": "your-key"}
    }
  }
}
```

## Flashcard Quality Principles

Andy Matuschak's five properties for effective prompts:
1. **Focused** - One idea per card
2. **Precise** - One unambiguous answer
3. **Consistent** - Same prompt retrieves same knowledge
4. **Tractable** - Answerable in seconds
5. **Effortful** - Requires genuine recall
