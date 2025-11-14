"""
AI agent tasks for the Mochi Donut system.

DEPRECATED: This file contains legacy Celery tasks using old LangGraph agents.
The system has migrated to Claude Agent SDK with ContentProcessorService.

For new implementations, use:
- src/app/services/content_processor.py (ContentProcessorService)
- src/app/agents/subagents.py (Claude SDK subagent definitions)

This file is kept temporarily for reference but will be removed in Phase 1 cleanup.
"""

import warnings
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import structlog

from app.tasks.celery_app import celery_app, TaskConfig
from app.services.cache import CacheService
# DEPRECATED: Legacy LangGraph agents removed - use Claude SDK instead
# from app.agents.orchestrator import OrchestratorAgent
# from app.agents.content_analyzer import ContentAnalyzerAgent
# from app.agents.prompt_generator import PromptGeneratorAgent
# from app.agents.quality_reviewer import QualityReviewerAgent
# from app.agents.refinement_agent import RefinementAgent
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.db.session import get_async_session
from app.schemas.prompt import PromptCreate, PromptUpdate

logger = structlog.get_logger()

warnings.warn(
    "agent_tasks.py is deprecated. Use ContentProcessorService with Claude Agent SDK instead.",
    DeprecationWarning,
    stacklevel=2
)


class AIAgentTask:
    """
    Base class for AI agent tasks with common utilities.

    DEPRECATED: This class used legacy LangGraph agents.
    Use ContentProcessorService for new implementations.
    """

    def __init__(self):
        self.cache_service = CacheService()
        self.content_repo = ContentRepository()
        self.prompt_repo = PromptRepository()
        # DEPRECATED: OrchestratorAgent removed - use ContentProcessorService
        # self.orchestrator = OrchestratorAgent()

    async def track_ai_usage(self, model: str, input_tokens: int, output_tokens: int, operation: str):
        """Track AI model usage for cost monitoring."""
        usage_data = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat(),
            "estimated_cost": self.calculate_cost(model, input_tokens, output_tokens),
        }

        # Store in cache for aggregation
        cache_key = f"ai_usage:{datetime.utcnow().strftime('%Y-%m-%d')}:{operation}:{model}"
        existing_data = await self.cache_service.get(cache_key)

        if existing_data:
            existing = json.loads(existing_data)
            existing["input_tokens"] += input_tokens
            existing["output_tokens"] += output_tokens
            existing["estimated_cost"] += usage_data["estimated_cost"]
            existing["request_count"] += 1
        else:
            usage_data["request_count"] = 1
            existing = usage_data

        await self.cache_service.set(cache_key, json.dumps(existing), ttl=86400 * 7)  # 7 days

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on 2025 GPT-5 pricing."""
        # GPT-5 pricing (per 1M tokens)
        pricing = {
            "gpt-5-nano": {"input": 0.05, "output": 0.40},
            "gpt-5-mini": {"input": 0.25, "output": 2.00},
            "gpt-5-standard": {"input": 1.25, "output": 10.00},
        }

        if model not in pricing:
            model = "gpt-5-mini"  # Default fallback

        rates = pricing[model]
        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]

        return input_cost + output_cost


@celery_app.task(bind=True, base=AIAgentTask, **TaskConfig.get_retry_config("ai"))
def generate_prompts(self, content_id: str, generation_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Generate high-quality prompts from content using AI agents.

    Args:
        content_id: Content UUID to process
        generation_options: Options for prompt generation

    Returns:
        Dict with generated prompts and metadata
    """
    task_logger = TaskConfig.get_task_logger("generate_prompts")
    generation_options = generation_options or {}

    try:
        task_logger.info("Starting prompt generation", content_id=content_id, task_id=self.request.id)

        # Get content from database
        async def get_content():
            async with get_async_session() as session:
                content = await self.content_repo.get_by_id(session, content_id)
                if not content:
                    raise ValueError(f"Content not found: {content_id}")
                return content

        content = asyncio.run(get_content())

        # Check cache for recent generation
        cache_key = f"prompts:generated:{content_id}"
        if not generation_options.get("force_regenerate", False):
            cached_result = asyncio.run(self.cache_service.get(cache_key))
            if cached_result:
                task_logger.info("Returning cached prompts", content_id=content_id)
                return json.loads(cached_result)

        # DEPRECATED: Legacy agents removed
        # Initialize agents
        # content_analyzer = ContentAnalyzerAgent()
        # prompt_generator = PromptGeneratorAgent()
        raise NotImplementedError(
            "Legacy generate_prompts task deprecated. "
            "Use ContentProcessorService.process_url() instead."
        )

        # Step 1: Analyze content
        task_logger.info("Analyzing content structure", content_id=content_id)
        analysis_result = asyncio.run(content_analyzer.analyze_content(
            content.markdown_content,
            metadata={
                "title": content.metadata.get("title", ""),
                "source_url": content.source_url,
                "content_type": "web_article",
            }
        ))

        if not analysis_result.get("success"):
            raise Exception(f"Content analysis failed: {analysis_result.get('error')}")

        # Track analysis usage
        asyncio.run(self.track_ai_usage(
            model="gpt-5-nano",
            input_tokens=analysis_result.get("input_tokens", 0),
            output_tokens=analysis_result.get("output_tokens", 0),
            operation="content_analysis"
        ))

        # Step 2: Generate prompts based on analysis
        task_logger.info("Generating prompts", content_id=content_id)

        prompt_config = {
            "target_count": generation_options.get("target_count", 8),
            "difficulty_level": generation_options.get("difficulty_level", "mixed"),
            "prompt_types": generation_options.get("prompt_types", [
                "factual", "conceptual", "procedural", "cloze"
            ]),
            "focus_areas": analysis_result.get("key_concepts", []),
            "content_complexity": analysis_result.get("complexity_score", 0.5),
        }

        generation_result = asyncio.run(prompt_generator.generate_prompts(
            content=content.markdown_content,
            analysis=analysis_result,
            config=prompt_config
        ))

        if not generation_result.get("success"):
            raise Exception(f"Prompt generation failed: {generation_result.get('error')}")

        # Track generation usage
        asyncio.run(self.track_ai_usage(
            model="gpt-5-mini",
            input_tokens=generation_result.get("input_tokens", 0),
            output_tokens=generation_result.get("output_tokens", 0),
            operation="prompt_generation"
        ))

        # Step 3: Store prompts in database
        generated_prompts = generation_result.get("prompts", [])

        async def store_prompts():
            prompt_records = []
            async with get_async_session() as session:
                for i, prompt_data in enumerate(generated_prompts):
                    prompt_create = PromptCreate(
                        content_id=content_id,
                        question=prompt_data["question"],
                        answer=prompt_data["answer"],
                        prompt_type=prompt_data.get("type", "factual"),
                        confidence_score=prompt_data.get("confidence", 0.5),
                        metadata={
                            "generation_method": "ai_agent",
                            "model_used": "gpt-5-mini",
                            "analysis_concepts": analysis_result.get("key_concepts", []),
                            "generation_order": i,
                            "difficulty_level": prompt_data.get("difficulty", "medium"),
                        }
                    )

                    prompt = await self.prompt_repo.create(session, prompt_create)
                    prompt_records.append(prompt)

                await session.commit()
                return prompt_records

        stored_prompts = asyncio.run(store_prompts())

        # Prepare result
        result = {
            "success": True,
            "content_id": content_id,
            "prompts_generated": len(stored_prompts),
            "prompt_ids": [p.id for p in stored_prompts],
            "analysis_summary": {
                "key_concepts": analysis_result.get("key_concepts", []),
                "complexity_score": analysis_result.get("complexity_score", 0),
                "content_length": len(content.markdown_content),
            },
            "generation_stats": {
                "model_used": "gpt-5-mini",
                "total_cost": generation_result.get("estimated_cost", 0),
                "processing_time": generation_result.get("processing_time", 0),
            },
        }

        # Cache result
        asyncio.run(self.cache_service.set(cache_key, json.dumps(result), ttl=3600))

        task_logger.info(
            "Prompt generation completed",
            content_id=content_id,
            prompts_count=len(stored_prompts)
        )

        # Trigger quality review asynchronously
        if generation_options.get("auto_review", True):
            review_task = review_prompt_quality.delay(
                prompt_ids=[p.id for p in stored_prompts],
                review_options={"threshold": 0.7}
            )
            result["quality_review_task_id"] = review_task.id

        return result

    except Exception as e:
        task_logger.error("Prompt generation failed", content_id=content_id, error=str(e))
        raise self.retry(countdown=120, max_retries=2, exc=e)


@celery_app.task(bind=True, base=AIAgentTask, **TaskConfig.get_retry_config("ai"))
def review_prompt_quality(self, prompt_ids: List[str], review_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Review prompt quality using AI quality reviewer.

    Args:
        prompt_ids: List of prompt IDs to review
        review_options: Quality review configuration

    Returns:
        Dict with quality review results and recommendations
    """
    task_logger = TaskConfig.get_task_logger("review_prompt_quality")
    review_options = review_options or {}

    try:
        task_logger.info("Starting quality review", prompt_count=len(prompt_ids), task_id=self.request.id)

        # Get prompts from database
        async def get_prompts():
            async with get_async_session() as session:
                prompts = []
                for prompt_id in prompt_ids:
                    prompt = await self.prompt_repo.get_by_id(session, prompt_id)
                    if prompt:
                        prompts.append(prompt)
                return prompts

        prompts = asyncio.run(get_prompts())

        if not prompts:
            raise ValueError("No valid prompts found for review")

        # DEPRECATED: Legacy quality reviewer removed
        # Initialize quality reviewer
        # quality_reviewer = QualityReviewerAgent()
        raise NotImplementedError(
            "Legacy review_prompt_quality task deprecated. "
            "Use ContentProcessorService with Claude SDK subagents instead."
        )

        # Review each prompt
        review_results = []
        quality_threshold = review_options.get("threshold", 0.7)

        for prompt in prompts:
            review_result = asyncio.run(quality_reviewer.review_prompt(
                question=prompt.question,
                answer=prompt.answer,
                prompt_type=prompt.prompt_type,
                context={
                    "content_id": prompt.content_id,
                    "generation_metadata": prompt.metadata,
                }
            ))

            if review_result.get("success"):
                review_data = {
                    "prompt_id": prompt.id,
                    "overall_score": review_result.get("overall_score", 0),
                    "dimension_scores": review_result.get("dimension_scores", {}),
                    "feedback": review_result.get("feedback", []),
                    "recommendations": review_result.get("recommendations", []),
                    "passes_threshold": review_result.get("overall_score", 0) >= quality_threshold,
                }
                review_results.append(review_data)

            # Track usage
            asyncio.run(self.track_ai_usage(
                model="gpt-5-standard",
                input_tokens=review_result.get("input_tokens", 0),
                output_tokens=review_result.get("output_tokens", 0),
                operation="quality_review"
            ))

        # Update prompts with quality scores
        async def update_quality_scores():
            async with get_async_session() as session:
                for review in review_results:
                    quality_metadata = {
                        **prompts[next(i for i, p in enumerate(prompts) if p.id == review["prompt_id"])].metadata,
                        "quality_review": {
                            "overall_score": review["overall_score"],
                            "dimension_scores": review["dimension_scores"],
                            "reviewed_at": datetime.utcnow().isoformat(),
                            "reviewer": "ai_agent",
                        }
                    }

                    await self.prompt_repo.update(
                        session,
                        review["prompt_id"],
                        {
                            "confidence_score": review["overall_score"],
                            "metadata": quality_metadata,
                        }
                    )

                await session.commit()

        asyncio.run(update_quality_scores())

        # Summary statistics
        passing_count = sum(1 for r in review_results if r["passes_threshold"])
        avg_score = sum(r["overall_score"] for r in review_results) / len(review_results)

        result = {
            "success": True,
            "reviewed_count": len(review_results),
            "passing_count": passing_count,
            "failing_count": len(review_results) - passing_count,
            "average_score": avg_score,
            "quality_threshold": quality_threshold,
            "reviews": review_results,
            "needs_refinement": [r["prompt_id"] for r in review_results if not r["passes_threshold"]],
        }

        task_logger.info(
            "Quality review completed",
            reviewed_count=len(review_results),
            passing_count=passing_count,
            average_score=avg_score
        )

        # Trigger refinement for failing prompts if requested
        if review_options.get("auto_refine", False) and result["needs_refinement"]:
            refinement_task = refine_prompts.delay(
                prompt_ids=result["needs_refinement"],
                refinement_options={"max_iterations": 2}
            )
            result["refinement_task_id"] = refinement_task.id

        return result

    except Exception as e:
        task_logger.error("Quality review failed", error=str(e))
        raise self.retry(countdown=120, max_retries=2, exc=e)


@celery_app.task(bind=True, base=AIAgentTask, **TaskConfig.get_retry_config("ai"))
def refine_prompts(self, prompt_ids: List[str], refinement_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Refine prompts based on quality feedback.

    Args:
        prompt_ids: List of prompt IDs to refine
        refinement_options: Refinement configuration

    Returns:
        Dict with refinement results
    """
    task_logger = TaskConfig.get_task_logger("refine_prompts")
    refinement_options = refinement_options or {}

    try:
        task_logger.info("Starting prompt refinement", prompt_count=len(prompt_ids), task_id=self.request.id)

        # Get prompts with quality feedback
        async def get_prompts_with_feedback():
            async with get_async_session() as session:
                prompts = []
                for prompt_id in prompt_ids:
                    prompt = await self.prompt_repo.get_by_id(session, prompt_id)
                    if prompt and "quality_review" in prompt.metadata:
                        prompts.append(prompt)
                return prompts

        prompts = asyncio.run(get_prompts_with_feedback())

        if not prompts:
            raise ValueError("No prompts with quality feedback found for refinement")

        # DEPRECATED: Legacy refinement agent removed
        # Initialize refinement agent
        # refinement_agent = RefinementAgent()
        # max_iterations = refinement_options.get("max_iterations", 2)
        raise NotImplementedError(
            "Legacy refine_prompts task deprecated. "
            "Use ContentProcessorService with Claude SDK refinement subagent instead."
        )

        refined_results = []

        for prompt in prompts:
            quality_feedback = prompt.metadata.get("quality_review", {})

            refinement_result = asyncio.run(refinement_agent.refine_prompt(
                original_question=prompt.question,
                original_answer=prompt.answer,
                feedback=quality_feedback.get("dimension_scores", {}),
                recommendations=quality_feedback.get("feedback", []),
                max_iterations=max_iterations
            ))

            if refinement_result.get("success"):
                # Create new version of the prompt
                async def create_refined_prompt():
                    async with get_async_session() as session:
                        refined_create = PromptCreate(
                            content_id=prompt.content_id,
                            question=refinement_result["refined_question"],
                            answer=refinement_result["refined_answer"],
                            prompt_type=prompt.prompt_type,
                            confidence_score=refinement_result.get("estimated_quality", 0.8),
                            version=prompt.version + 1,
                            metadata={
                                **prompt.metadata,
                                "refinement": {
                                    "original_prompt_id": prompt.id,
                                    "refinement_iterations": refinement_result.get("iterations", 1),
                                    "improvements": refinement_result.get("improvements", []),
                                    "refined_at": datetime.utcnow().isoformat(),
                                }
                            }
                        )

                        refined_prompt = await self.prompt_repo.create(session, refined_create)
                        await session.commit()
                        return refined_prompt

                refined_prompt = asyncio.run(create_refined_prompt())

                refined_results.append({
                    "original_id": prompt.id,
                    "refined_id": refined_prompt.id,
                    "iterations": refinement_result.get("iterations", 1),
                    "improvements": refinement_result.get("improvements", []),
                    "estimated_quality": refinement_result.get("estimated_quality", 0.8),
                })

                # Track usage
                asyncio.run(self.track_ai_usage(
                    model="gpt-5-mini",
                    input_tokens=refinement_result.get("input_tokens", 0),
                    output_tokens=refinement_result.get("output_tokens", 0),
                    operation="prompt_refinement"
                ))

        result = {
            "success": True,
            "refined_count": len(refined_results),
            "max_iterations": max_iterations,
            "refinements": refined_results,
            "avg_iterations": sum(r["iterations"] for r in refined_results) / len(refined_results) if refined_results else 0,
        }

        task_logger.info(
            "Prompt refinement completed",
            refined_count=len(refined_results),
            avg_iterations=result["avg_iterations"]
        )

        return result

    except Exception as e:
        task_logger.error("Prompt refinement failed", error=str(e))
        raise self.retry(countdown=120, max_retries=1, exc=e)


@celery_app.task(bind=True, base=AIAgentTask, **TaskConfig.get_retry_config("maintenance"))
def track_ai_costs(self, period: str = "daily") -> Dict[str, Any]:
    """
    Aggregate and track AI usage costs.

    Args:
        period: Tracking period (daily, weekly, monthly)

    Returns:
        Dict with cost tracking results
    """
    task_logger = TaskConfig.get_task_logger("track_ai_costs")

    try:
        task_logger.info("Starting AI cost tracking", period=period, task_id=self.request.id)

        # Calculate date range
        now = datetime.utcnow()
        if period == "daily":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == "weekly":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
            end_date = start_date + timedelta(days=7)
        elif period == "monthly":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = start_date.replace(month=start_date.month + 1) if start_date.month < 12 else start_date.replace(year=start_date.year + 1, month=1)
            end_date = next_month
        else:
            raise ValueError(f"Invalid period: {period}")

        # Aggregate usage from cache
        cost_summary = {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "models": {},
            "operations": {},
            "total_cost": 0.0,
            "total_tokens": {"input": 0, "output": 0},
            "request_count": 0,
        }

        # This would scan cache keys and aggregate data
        # Implementation depends on Redis scanning capabilities
        # For now, return placeholder structure

        task_logger.info("AI cost tracking completed", period=period, total_cost=cost_summary["total_cost"])
        return cost_summary

    except Exception as e:
        task_logger.error("AI cost tracking failed", period=period, error=str(e))
        raise self.retry(countdown=300, max_retries=1, exc=e)


@celery_app.task(bind=True, **TaskConfig.get_retry_config("ai"))
def orchestrate_content_pipeline(self, content_id: str, pipeline_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Orchestrate the complete AI pipeline for content processing.

    Args:
        content_id: Content to process through the pipeline
        pipeline_options: Pipeline configuration options

    Returns:
        Dict with complete pipeline results
    """
    task_logger = TaskConfig.get_task_logger("orchestrate_content_pipeline")
    pipeline_options = pipeline_options or {}

    try:
        task_logger.info("Starting content pipeline orchestration", content_id=content_id, task_id=self.request.id)

        # Chain the tasks in the correct order
        pipeline_chain = (
            generate_prompts.s(content_id, pipeline_options.get("generation_options", {})) |
            review_prompt_quality.s(review_options=pipeline_options.get("review_options", {})) |
            refine_prompts.s(refinement_options=pipeline_options.get("refinement_options", {}))
        )

        # Execute the pipeline
        pipeline_result = pipeline_chain.apply_async()
        final_result = pipeline_result.get(timeout=900)  # 15 minute timeout

        task_logger.info("Content pipeline orchestration completed", content_id=content_id)
        return final_result

    except Exception as e:
        task_logger.error("Content pipeline orchestration failed", content_id=content_id, error=str(e))
        raise self.retry(countdown=180, max_retries=1, exc=e)