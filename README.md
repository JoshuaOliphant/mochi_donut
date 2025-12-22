# Mochi Donut

An MCP server that converts web content into high-quality Mochi flashcards following Andy Matuschak's spaced repetition principles.

## Features

- **fetch_url** - Extract clean markdown from any URL via JinaAI Reader
- **list_decks** - List your Mochi decks
- **create_cards** - Create flashcards in Mochi (single or batch)
- Built-in resources with Matuschak's flashcard writing principles
- Prompt templates for generating and reviewing flashcards

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Mochi API key from https://app.mochi.cards/settings/api

### Installation

```bash
git clone https://github.com/JoshuaOliphant/mochi_donut.git
cd mochi_donut
uv sync
```

### Running the Server

```bash
uv run python -m mochi_donut.server
```

### Installing in Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "mochi-donut": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mochi_donut", "python", "-m", "mochi_donut.server"],
      "env": {
        "MOCHI_API_KEY": "your-mochi-api-key"
      }
    }
  }
}
```

Restart Claude Code, then you can say things like:
- "Create flashcards from this article: https://example.com/article"
- "List my Mochi decks"

## Usage Example

Once installed in Claude Code:

1. Provide a URL to create flashcards from
2. Claude fetches the content using `fetch_url`
3. Claude reads the `matuschak://principles` resource for guidance
4. Claude generates flashcards following those principles
5. Claude uses `list_decks` to find your target deck
6. Claude creates the cards using `create_cards`

## Development

```bash
# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_server.py::TestFetchUrlTool -v
```

## Architecture

Minimal MCP server built with [FastMCP](https://gofastmcp.com):

```
src/mochi_donut/
├── __init__.py     # Package entry point
└── server.py       # MCP server with tools, resources, and prompts
```

Dependencies: `fastmcp`, `httpx`

## License

MIT
