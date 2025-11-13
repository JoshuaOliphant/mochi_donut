# ABOUTME: Content processing service using Claude Agent SDK for orchestrating multi-agent workflow.
# ABOUTME: Replaces complex LangGraph orchestrator with simple SDK-based approach for flashcard generation.
"""
Content processing service using Claude Agent SDK.
Orchestrates multi-agent workflow for flashcard generation.
"""

import uuid
from typing import Dict, Any
from datetime import datetime

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

from src.app.agents.subagents import get_subagent_definitions
from src.app.mcp_tools import get_flat_tool_list


class ContentProcessorService:
    """
    Service for processing content into flashcards using Claude Agent SDK.

    This replaces the complex LangGraph orchestrator with a simple SDK-based approach.
    The service orchestrates specialized subagents to analyze content, generate prompts,
    review quality, and refine low-quality prompts iteratively.
    """

    def __init__(
        self,
        quality_threshold: float = 0.7,
        max_iterations: int = 3
    ):
        """
        Initialize the content processor service.

        Args:
            quality_threshold: Minimum quality score (0.0-1.0) for prompts
            max_iterations: Maximum refinement iterations for low-quality prompts
        """
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations

        # Get all available MCP tools
        all_tools = get_flat_tool_list()
        tool_names = [tool.name for tool in all_tools]

        # Add built-in Claude Code tools
        allowed_tools = tool_names + ['Read', 'Grep', 'Glob']

        # Configure Claude Agent SDK options
        self.agent_options = ClaudeAgentOptions(
            system_prompt=self._get_system_prompt(),
            agents=get_subagent_definitions(),
            # MCP servers are defined in the tools themselves via @tool decorator
            # The SDK will automatically discover them
            allowed_tools=allowed_tools,
            permission_mode='bypassPermissions',  # For automated processing
            cwd='.'
        )

    def _get_system_prompt(self) -> str:
        """Get the main orchestrator system prompt."""
        return f"""You are the orchestrator for a spaced repetition learning system.

Your goal: Convert content into high-quality flashcards following Andy Matuschak's principles.

Available subagents:
- content-analyzer: Extracts key concepts and assesses complexity
- prompt-generator: Creates diverse, high-quality prompts
- quality-reviewer: Scores prompts against quality criteria
- refinement-agent: Improves low-quality prompts

Quality standards:
- Quality threshold: {self.quality_threshold}
- Maximum iterations: {self.max_iterations}
- Target: 5-15 prompts per content piece

Process workflow:
1. Fetch content and convert to markdown (use fetch_markdown tool)
2. Store in vector database (use store_content tool)
3. Delegate to content-analyzer to extract concepts
4. Delegate to prompt-generator to create prompts
5. Delegate to quality-reviewer to score quality
6. If quality below threshold and iterations remaining:
   - Delegate to refinement-agent to improve prompts
   - Return to step 5
7. Save final prompts to database (use save_prompts tool)
8. Return final results

Be efficient, thorough, and maintain high quality standards.
"""

    async def process_url(
        self,
        url: str,
        auto_approve: bool = False
    ) -> Dict[str, Any]:
        """
        Process a URL into flashcards.

        This method orchestrates the complete workflow from content fetching
        through quality refinement, delegating to specialized subagents at each step.

        Args:
            url: URL to process
            auto_approve: If True and quality met, auto-send to Mochi

        Returns:
            Dict with workflow results including:
            - workflow_id: Unique workflow execution ID
            - content_id: Unique content ID
            - status: "completed" or "failed"
            - url: The processed URL
            - started_at: ISO timestamp when processing started
            - completed_at: ISO timestamp when processing completed
            - duration_seconds: Total processing time
            - cost_usd: Estimated cost in USD
            - messages: Last 5 messages from the workflow
            - result: Final workflow result data
        """
        content_id = str(uuid.uuid4())
        workflow_id = str(uuid.uuid4())
        started_at = datetime.now()

        # Create the workflow prompt
        workflow_prompt = f"""
Process this URL for spaced repetition learning: {url}

Content ID: {content_id}
Workflow ID: {workflow_id}
Auto-approve to Mochi: {auto_approve}

Execute the complete workflow:

1. Fetch and convert URL to markdown using fetch_markdown tool
2. Save to database using save_content tool with content_id
3. Store in Chroma using store_content tool for semantic search
4. Delegate to content-analyzer subagent to analyze the markdown and extract key concepts
5. Delegate to prompt-generator subagent to create 5-15 prompts based on the concepts
6. Delegate to quality-reviewer subagent to score each prompt
7. Check overall quality:
   - If average score >= {self.quality_threshold} AND all prompts >= {self.quality_threshold}:
     → Proceed to step 8
   - Else if iterations < {self.max_iterations}:
     → Delegate to refinement-agent to improve low-scoring prompts
     → Return to step 6 with refined prompts
   - Else:
     → Proceed with current prompts (max iterations reached)
8. Save final prompts using save_prompts tool
9. If auto_approve is True AND quality threshold met:
   → Create cards in Mochi using create_card tool
10. Return comprehensive results including:
    - Number of prompts generated
    - Average quality score
    - Iterations performed
    - Total cost in USD
    - List of all final prompts with their quality scores

Be thorough, maintain quality standards, and provide detailed results.
"""

        try:
            # Execute workflow via Claude Agent SDK
            async with ClaudeSDKClient(self.agent_options) as client:
                await client.connect()

                # Collect all messages
                result_data = None
                messages = []

                async for message in client.query(workflow_prompt):
                    messages.append(message)

                    if message.type == "result":
                        result_data = message
                        break

                # Parse results
                completed_at = datetime.now()
                duration = (completed_at - started_at).total_seconds()

                # Extract metrics from result
                cost_usd = 0.0
                if hasattr(result_data, 'usage') and result_data.usage:
                    # Calculate cost based on token usage
                    cost_usd = self._calculate_cost(result_data.usage)

                return {
                    "workflow_id": workflow_id,
                    "content_id": content_id,
                    "status": "completed",
                    "url": url,
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                    "duration_seconds": duration,
                    "cost_usd": cost_usd,
                    "messages": [str(m) for m in messages[-5:]],  # Last 5 messages
                    "result": result_data.result if result_data else None
                }

        except Exception as e:
            return {
                "workflow_id": workflow_id,
                "content_id": content_id,
                "status": "failed",
                "error": str(e),
                "duration_seconds": (datetime.now() - started_at).total_seconds()
            }

    def _calculate_cost(self, usage: Dict[str, Any]) -> float:
        """
        Calculate approximate cost based on token usage.

        Cost calculation uses weighted average pricing across model tiers:
        - Haiku: $0.25/1M input, $1.25/1M output
        - Sonnet: $3.00/1M input, $15.00/1M output
        - Opus: $15.00/1M input, $75.00/1M output

        This is a simplified estimate using Sonnet pricing as the middle ground.
        Actual costs depend on which models were used by subagents.

        Args:
            usage: Dict with 'input_tokens' and 'output_tokens' keys

        Returns:
            Estimated cost in USD
        """
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)

        # Assume average of Sonnet pricing (middle tier)
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0

        return input_cost + output_cost
