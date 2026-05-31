# ABOUTME: Mochi Donut MCP server package
# ABOUTME: Exposes the main server entry point
"""
Mochi Donut - Convert web content into Mochi flashcards via MCP.

This package provides an MCP server that helps create high-quality
flashcards following Andy Matuschak's spaced repetition principles.
"""

from mochi_donut.server import __version__, main, mcp

__all__ = ["__version__", "mcp", "main"]
