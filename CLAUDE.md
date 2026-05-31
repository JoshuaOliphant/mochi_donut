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

Core business logic lives in `_impl` functions (e.g., `_fetch_url_impl`) which are wrapped by `@mcp.tool` decorators. Test the `_impl` functions directly, or call the decorated wrappers directly — under FastMCP 3.x the `@mcp.tool`/`@mcp.resource`/`@mcp.prompt` decorators return the original function unchanged, so `fetch_url(...)`, `get_principles()`, etc. are all directly callable.

The Mochi API uses **HTTP Basic auth** (the API key is the username, password blank). Cards are created as two-sided markdown: a single `content` field with the front and back separated by a `---` line (`"Question\n---\nAnswer"`), which works on any deck without a template. Tags go in the `manual-tags` field.

## Development Commands

```bash
# Run the MCP server
uv run python -m mochi_donut.server

# Run all tests (enforces 100% coverage; fails under threshold)
uv run pytest

# Run specific test class
uv run pytest tests/test_server.py::TestFetchUrlTool -v

# Run single test
uv run pytest tests/test_server.py::TestFetchUrlTool::test_fetch_url_success -v
```

## Coverage Rule (REQUIRED)

This project enforces **100% line and branch coverage** of `src/mochi_donut`.
The threshold is wired into `pytest.ini` via `--cov-fail-under=100`, so any
drop below 100% fails `uv run pytest`.

Whenever you add or change code:
1. Add tests that cover every new line and branch — including error paths,
   wrapper functions, and `__main__` entry points.
2. Run `uv run pytest` and confirm the coverage report shows 100%.
3. If a line is genuinely unreachable, delete it rather than excluding it
   from coverage. Do **not** add `# pragma: no cover` to paper over gaps.
4. Prefer making code testable (extract `_impl` helpers, dependency-inject
   side effects) over carving out exemptions.

Under FastMCP 3.x the `@mcp.tool`, `@mcp.resource`, and `@mcp.prompt`
decorators return the **original function** unchanged (not a
`FunctionTool`/`FunctionResource`/`FunctionPrompt` wrapper as in 2.x). To
cover the body, import the decorated function and call it directly — see
`tests/test_server.py::TestToolWrappers` for the pattern. To assert a
component is *registered*, use the async public API: `await
mcp.get_tool(name)`, `await mcp.get_resource(uri)`, `await
mcp.get_prompt(name)` (the old private `_tool_manager`/`_resource_manager`/
`_prompt_manager` attributes were removed in 3.x).

## Versioning

The version is defined **once**, in `pyproject.toml`. Both
`mochi_donut.__version__` and the running server's advertised version
(`FastMCP(..., version=__version__)`, surfaced as `serverInfo.version` in the
MCP handshake) read it from the installed package metadata via
`importlib.metadata.version("mochi-donut")`, so they never drift. To cut a
release: bump `version` in `pyproject.toml`, add a `CHANGELOG.md` entry, and
tag the commit (`vX.Y.Z`). Pre-1.0, minor bumps may include behavioral changes.

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
