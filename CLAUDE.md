# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Mochi Donut is an MCP server that converts web content into high-quality Mochi flashcards following Andy Matuschak's spaced repetition principles.

## Architecture

This is a **minimal MCP server** - no database, no web framework, no background tasks. Just tools, resources, and prompts.

```
src/mochi_donut/
├── __init__.py     # Package entry point
└── server.py       # MCP server with tools, resources, and prompts
```

### MCP Components

**Tools** (actions the agent can take):
- `fetch_url` - Fetch URL content as markdown via JinaAI Reader
- `list_decks` - List available Mochi decks
- `create_cards` - Create flashcards in Mochi (single or batch)

**Resources** (static data for context):
- `matuschak://principles` - Andy Matuschak's flashcard writing principles
- `matuschak://examples` - Example good/bad flashcards

**Prompts** (reusable templates):
- `generate_flashcards` - Template for generating cards from content
- `review_flashcards` - Template for reviewing draft cards

### Dependencies

Minimal dependencies:
- `fastmcp` - MCP server framework
- `httpx` - HTTP client for JinaAI and Mochi APIs

## Development Commands

### Running the Server

```bash
# Run directly
uv run python -m mochi_donut.server

# Or via entry point
uv run mochi-donut
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_server.py::TestFetchUrlTool -v
```

### Installing in Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "mochi-donut": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mochi_donut", "python", "-m", "mochi_donut.server"]
    }
  }
}
```

## Environment Variables

Required:
- `MOCHI_API_KEY` - Your Mochi API key from https://app.mochi.cards/settings/api

## Typical Workflow

When using Mochi Donut through Claude Code:

1. User provides a URL
2. Use `fetch_url` to get markdown content
3. Read `matuschak://principles` resource for guidance
4. Generate flashcards following those principles
5. Use `list_decks` to find target deck
6. Use `create_cards` to save to Mochi

## Quality Principles

Following Andy Matuschak's principles for effective flashcards:

1. **Focused** - Each card tests one idea
2. **Precise** - Questions have one unambiguous answer
3. **Consistent** - Same prompt retrieves same knowledge
4. **Tractable** - Answerable within seconds
5. **Effortful** - Requires genuine recall, not pattern matching

## External Resources

- [Mochi API Documentation](https://mochi.cards/docs/api)
- [JinaAI Reader API](https://jina.ai/reader)
- [Andy Matuschak's Prompt Guide](https://andymatuschak.org/prompts/)
- [FastMCP Documentation](https://gofastmcp.com)
