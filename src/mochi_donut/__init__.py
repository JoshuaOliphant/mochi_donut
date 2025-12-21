# ABOUTME: Mochi Donut MCP server package
# ABOUTME: Exposes the main server entry point
"""
Mochi Donut - Convert web content into Mochi flashcards via MCP.

This package provides an MCP server that helps create high-quality
flashcards following Andy Matuschak's spaced repetition principles.
"""

from mochi_donut.server import mcp, main

__version__ = "0.2.0"
__all__ = ["mcp", "main"]
