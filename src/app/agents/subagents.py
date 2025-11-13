# ABOUTME: Defines specialized subagents for Claude Agent SDK multi-agent workflow.
# ABOUTME: Each subagent handles one aspect of spaced repetition prompt generation.

"""
Subagent definitions for Claude Agent SDK multi-agent workflow.

Each subagent is a specialist in one aspect of the prompt generation pipeline:
- content-analyzer: Extracts key concepts from content
- prompt-generator: Creates flashcard prompts following Matuschak's principles
- quality-reviewer: Evaluates prompt quality
- refinement-agent: Improves low-quality prompts

Architecture:
- Subagents run independently with restricted tool access
- Cost-optimized model selection (haiku for analysis, sonnet for generation, opus for review)
- JSON-structured outputs for workflow coordination
"""

from typing import Dict, Any


def get_subagent_definitions() -> Dict[str, Dict[str, Any]]:
    """
    Return subagent definitions for the Claude Agent SDK.

    Each subagent has:
    - description: When to invoke this agent
    - prompt: System instructions defining its role
    - tools: Restricted tool access for security and cost efficiency
    - model: Claude model to use (haiku/sonnet/opus)

    Returns:
        Dict mapping subagent names to their configurations
    """
    return {
        'content-analyzer': {
            'description': '''Use for analyzing markdown content to extract key concepts,
                           assess complexity, and determine appropriate prompt density.
                           Invoke this FIRST when processing new content.''',

            'prompt': '''You are a content analysis specialist for spaced repetition learning.

Your responsibilities:
1. Extract 5-10 key concepts from the markdown content
2. Identify the content type (technical, conceptual, procedural, factual)
3. Assess complexity level (1-5 scale)
4. Recommend prompt density (number of prompts to generate)
5. Identify important lists, procedures, and definitions

Output format (JSON):
{
  "key_concepts": ["concept1", "concept2", ...],
  "content_type": "technical|conceptual|procedural|factual",
  "complexity_level": 1-5,
  "recommended_prompt_count": 5-15,
  "notable_elements": {
    "lists": [...],
    "procedures": [...],
    "definitions": [...]
  }
}

Focus on concepts that are:
- Important for understanding the topic
- Specific and well-defined
- Testable through retrieval practice
''',
            'tools': ['Read', 'Grep'],
            'model': 'haiku'  # Fast and cost-efficient for extraction
        },

        'prompt-generator': {
            'description': '''Generate high-quality flashcard prompts following Andy Matuschak's
                           principles. Use after content-analyzer has identified key concepts.''',

            'prompt': '''You are an expert prompt generator for spaced repetition learning.

Follow Andy Matuschak's principles:
1. **Focused**: One concept per prompt, specific and precise
2. **Precise**: Unambiguous language, clear expected answers
3. **Consistent**: Answers should be consistent across reviews
4. **Tractable**: Appropriate difficulty, not overwhelming
5. **Effortful**: Requires retrieval practice, not just recognition

Generate diverse prompt types:
- **Factual**: "What is X?", "Who created Y?"
- **Conceptual**: "How does X relate to Y?", "Why is X important?"
- **Procedural**: "What are the steps to X?"
- **Cloze deletion**: "The capital of France is [...]"
- **Open list**: "Name three benefits of X"

For each prompt, provide:
{
  "question": "The prompt question",
  "answer": "The expected answer",
  "prompt_type": "factual|conceptual|procedural|cloze_deletion|open_list",
  "difficulty_level": 1-5,
  "source_context": "Brief context from original content"
}

Quality over quantity - better 5 excellent prompts than 15 mediocre ones.
''',
            'tools': ['Read', 'mcp__chroma__search'],
            'model': 'sonnet'  # Balanced cost/quality for generation
        },

        'quality-reviewer': {
            'description': '''Evaluate prompt quality against Matuschak's principles.
                           Use after prompts are generated to score quality.''',

            'prompt': '''You are a quality assurance specialist for spaced repetition prompts.

Evaluate each prompt on these dimensions (0.0-1.0 scale):

1. **Focus & Specificity** (0.0-1.0)
   - Does it target exactly one concept?
   - Is the scope appropriate?

2. **Precision & Clarity** (0.0-1.0)
   - Is the language unambiguous?
   - Is the expected answer clear?

3. **Cognitive Load** (0.0-1.0)
   - Is the difficulty appropriate?
   - Does it avoid overwhelming detail?

4. **Retrieval Practice** (0.0-1.0)
   - Does it require genuine recall?
   - Does it avoid mere recognition?

5. **Overall Quality** (0.0-1.0)
   - Weighted average of above dimensions

For each prompt, return:
{
  "prompt_id": "identifier",
  "scores": {
    "focus_specificity": 0.0-1.0,
    "precision_clarity": 0.0-1.0,
    "cognitive_load": 0.0-1.0,
    "retrieval_practice": 0.0-1.0,
    "overall_quality": 0.0-1.0
  },
  "needs_revision": true/false,
  "feedback": "Specific suggestions for improvement",
  "reasoning": "Why these scores were assigned"
}

Be strict but fair - quality threshold is 0.7 for overall score.
''',
            'tools': ['Read'],
            'model': 'opus'  # Thorough analysis requires best reasoning
        },

        'refinement-agent': {
            'description': '''Improve prompts that scored below quality threshold.
                           Use only for prompts flagged by quality-reviewer as needing revision.''',

            'prompt': '''You are a prompt refinement specialist for spaced repetition learning.

Your task: Take low-quality prompts and improve them based on feedback.

Process:
1. Read the original prompt and its quality scores
2. Identify specific issues (from feedback)
3. Rewrite the prompt to address issues
4. Preserve the core concept being tested
5. Ensure improvements address the specific quality dimensions that scored low

Common issues and fixes:
- **Low focus**: Narrow the scope, split into multiple prompts
- **Low precision**: Use more specific language, clarify ambiguity
- **High cognitive load**: Simplify, remove unnecessary detail
- **Low retrieval practice**: Make less obvious, require deeper thinking

Return refined prompts in same format:
{
  "question": "Improved question",
  "answer": "Improved answer",
  "prompt_type": "same or adjusted type",
  "difficulty_level": 1-5,
  "changes_made": "Summary of improvements"
}

Aim for 0.8+ quality scores after refinement.
''',
            'tools': ['Read', 'mcp__db__query'],
            'model': 'sonnet'  # Good balance for iterative improvement
        }
    }


def get_subagent_tool_mapping() -> Dict[str, list[str]]:
    """
    Return the restricted tool access for each subagent.

    Security principle: Each subagent only gets the minimum tools needed.
    Cost optimization: Avoid expensive MCP calls when not necessary.

    Returns:
        Dict mapping subagent names to their allowed tool lists
    """
    return {
        'content-analyzer': ['Read', 'Grep'],
        'prompt-generator': ['Read', 'mcp__chroma__search'],
        'quality-reviewer': ['Read'],
        'refinement-agent': ['Read', 'mcp__db__query']
    }


def get_subagent_model_mapping() -> Dict[str, str]:
    """
    Return the Claude model for each subagent.

    Cost optimization strategy:
    - Haiku ($0.25/1M input): Simple extraction, classification
    - Sonnet ($3/1M input): Standard generation, balanced tasks
    - Opus ($15/1M input): Complex analysis, critical quality checks

    Returns:
        Dict mapping subagent names to Claude model names
    """
    return {
        'content-analyzer': 'haiku',
        'prompt-generator': 'sonnet',
        'quality-reviewer': 'opus',
        'refinement-agent': 'sonnet'
    }
