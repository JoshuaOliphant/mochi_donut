# ABOUTME: Mochi Donut MCP server package
# ABOUTME: Exposes the main server entry point
"""
Mochi Donut - Convert web content into Mochi flashcards via MCP.

This package provides an MCP server that helps create high-quality
flashcards following Andy Matuschak's spaced repetition principles.
"""

from mochi_donut.server import main, mcp

__version__ = "0.3.0"
__all__ = ["mcp", "main"]
