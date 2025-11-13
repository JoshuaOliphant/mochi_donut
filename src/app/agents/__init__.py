# Multi-Agent AI Architecture for Mochi Donut
"""
Multi-agent AI system for spaced repetition prompt generation using LangGraph and LangChain.

This module implements an Orchestrator-Workers pattern with specialized agents:
- OrchestratorAgent: Coordinates workflow between agents
- ContentAnalyzerAgent: Extracts key concepts using GPT-5-nano
- PromptGeneratorAgent: Creates prompts following Matuschak's principles using GPT-5-mini
- QualityReviewerAgent: Evaluates prompt quality using GPT-5-standard
- RefinementAgent: Iteratively improves prompts using GPT-5-mini
"""

from .base import AgentBase, AgentState, AgentError, CostTracker
from .content_analyzer import ContentAnalyzerAgent
from .prompt_generator import PromptGeneratorAgent
from .quality_reviewer import QualityReviewerAgent
from .refinement_agent import RefinementAgent
from .orchestrator import OrchestratorAgent
from .workflow import PromptGenerationWorkflow
from .service import AgentOrchestratorService

__all__ = [
    "AgentBase",
    "AgentState",
    "AgentError",
    "CostTracker",
    "ContentAnalyzerAgent",
    "PromptGeneratorAgent",
    "QualityReviewerAgent",
    "RefinementAgent",
    "OrchestratorAgent",
    "PromptGenerationWorkflow",
    "AgentOrchestratorService",
]