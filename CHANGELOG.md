# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the project is pre-1.0, minor version bumps may include behavioral
changes.

The version is defined once in `pyproject.toml`; the package and the running
MCP server (`serverInfo.version`) both read it from the installed package
metadata, so it never drifts.

## [0.3.1]

### Fixed
- **Mochi API 404s**: `list_decks` and `create_cards` now request
  `/api/decks/` and `/api/cards/` with the trailing slash Mochi's router
  requires. Without it the router returns `404 Not Found` even with a valid
  API key.

## [0.3.0]

### Changed
- Upgraded to **FastMCP 3.x** (from 2.x) and refreshed all dependencies.
- **Mochi API**: authenticate with HTTP Basic auth (API key as username,
  blank password) instead of a Bearer token.
- **Mochi cards** are now created as two-sided markdown using a single
  `content` field with a `---` separator (`"Question\n---\nAnswer"`), so they
  render on any deck without a template. Tags are sent in the `manual-tags`
  field.

### Added
- The MCP server now advertises its version to clients via FastMCP's
  `version` argument, sourced from the package metadata.
- Development tooling and CI: `ruff`, `mypy`, `ty`, and `bandit`, with a
  Code Quality job that runs them.

## [0.2.0]

- Initial published version: a minimal MCP server (tools `fetch_url`,
  `list_decks`, `create_cards`; Matuschak resources and prompts) on FastMCP 2.x.
