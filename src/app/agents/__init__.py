# Multi-Agent AI Architecture for Mochi Donut
"""
Multi-agent AI system for spaced repetition prompt generation using Claude Agent SDK.

This module implements a subagent-based pattern with specialized agents:
- content-analyzer: Extracts key concepts (haiku)
- prompt-generator: Creates prompts following Matuschak's principles (sonnet)
- quality-reviewer: Evaluates prompt quality (opus)
- refinement-agent: Iteratively improves prompts (sonnet)

Note: Legacy LangGraph agents (base.py, orchestrator.py, etc.) are deprecated
and will be removed in Phase 1 cleanup.
"""

from .subagents import (
    get_subagent_definitions,
    get_subagent_tool_mapping,
    get_subagent_model_mapping
)

__all__ = [
    "get_subagent_definitions",
    "get_subagent_tool_mapping",
    "get_subagent_model_mapping",
]