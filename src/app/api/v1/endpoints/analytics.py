# Analytics API Endpoints
"""
FastAPI endpoints for analytics, metrics, and reporting.
Provides insights into content processing, prompt quality, and system performance.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_content_repository,
    get_prompt_repository,
    APIResponse
)
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.db.models import SourceType, PromptType, ProcessingStatus


router = APIRouter()


@router.get(
    "/dashboard",
    response_model=Dict[str, Any],
    summary="Get Dashboard Metrics",
    description="Get key metrics for the main dashboard"
)
async def get_dashboard_metrics(
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Get dashboard metrics and KPIs."""
    try:
        # Get current metrics
        content_stats = await content_repo.get_statistics()
        prompt_stats = await prompt_repo.get_statistics()

        # Calculate growth metrics (last 7 days vs previous 7 days)
        now = datetime.utcnow()
        current_week_start = now - timedelta(days=7)
        previous_week_start = now - timedelta(days=14)

        current_week_content = await content_repo.count_by_date_range(
            current_week_start, now
        )
        previous_week_content = await content_repo.count_by_date_range(
            previous_week_start, current_week_start
        )

        current_week_prompts = await prompt_repo.count_by_date_range(
            current_week_start, now
        )
        previous_week_prompts = await prompt_repo.count_by_date_range(
            previous_week_start, current_week_start
        )

        # Calculate growth rates
        content_growth = (
            ((current_week_content - previous_week_content) / previous_week_content * 100)
            if previous_week_content > 0 else 0
        )
        prompt_growth = (
            ((current_week_prompts - previous_week_prompts) / previous_week_prompts * 100)
            if previous_week_prompts > 0 else 0
        )

        # Get recent activity
        recent_activity = await content_repo.get_recent_activity(limit=10)

        return APIResponse.success(
            data={
                "overview": {
                    "total_content": content_stats.get("total_content", 0),
                    "total_prompts": prompt_stats.get("total_prompts", 0),
                    "content_growth": round(content_growth, 2),
                    "prompt_growth": round(prompt_growth, 2),
                    "avg_quality_score": prompt_stats.get("quality_stats", {}).get("average", 0)
                },
                "content_stats": content_stats,
                "prompt_stats": prompt_stats,
                "recent_activity": recent_activity
            },
            message="Dashboard metrics retrieved"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard metrics"
        )


@router.get(
    "/content/processing-performance",
    response_model=Dict[str, Any],
    summary="Get Content Processing Performance",
    description="Get metrics about content processing performance and bottlenecks"
)
async def get_processing_performance(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    content_repo: ContentRepository = Depends(get_content_repository)
) -> Dict[str, Any]:
    """Get content processing performance metrics."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get processing metrics
        processing_stats = await content_repo.get_processing_performance(
            start_date, end_date
        )

        return APIResponse.success(
            data=processing_stats,
            message="Processing performance metrics retrieved"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get processing performance"
        )


@router.get(
    "/prompts/quality-trends",
    response_model=Dict[str, Any],
    summary="Get Prompt Quality Trends",
    description="Get trends in prompt quality over time"
)
async def get_quality_trends(
    days: int = Query(30, ge=7, le=365, description="Number of days to analyze"),
    group_by: str = Query("day", regex="^(hour|day|week)$", description="Grouping interval"),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Get prompt quality trends over time."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get quality trends
        quality_trends = await prompt_repo.get_quality_trends(
            start_date, end_date, group_by
        )

        return APIResponse.success(
            data={
                "period": f"{days} days",
                "group_by": group_by,
                "trends": quality_trends
            },
            message="Quality trends retrieved"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quality trends"
        )


@router.get(
    "/costs/ai-usage",
    response_model=Dict[str, Any],
    summary="Get AI Usage Costs",
    description="Get AI model usage and associated costs"
)
async def get_ai_usage_costs(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Get AI usage costs and optimization insights."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get AI usage stats
        ai_usage = await content_repo.get_ai_usage_stats(start_date, end_date)
        cost_breakdown = await prompt_repo.get_cost_breakdown(start_date, end_date)

        # Calculate optimization recommendations
        recommendations = []

        # Check for expensive models being overused
        if cost_breakdown.get("gpt5_standard_cost", 0) > cost_breakdown.get("total_cost", 1) * 0.5:
            recommendations.append({
                "type": "cost_optimization",
                "message": "Consider using GPT-5 Standard more selectively for quality review",
                "potential_savings": "up to 40%"
            })

        # Check for caching opportunities
        cache_hit_rate = ai_usage.get("cache_hit_rate", 0)
        if cache_hit_rate < 0.7:
            recommendations.append({
                "type": "caching",
                "message": "Low cache hit rate detected. Review content deduplication",
                "current_rate": f"{cache_hit_rate:.1%}"
            })

        return APIResponse.success(
            data={
                "period": f"{days} days",
                "ai_usage": ai_usage,
                "cost_breakdown": cost_breakdown,
                "recommendations": recommendations
            },
            message="AI usage costs retrieved"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get AI usage costs"
        )


@router.get(
    "/content/source-analysis",
    response_model=Dict[str, Any],
    summary="Get Content Source Analysis",
    description="Analyze content performance by source type"
)
async def get_source_analysis(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Analyze content performance by source type."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get source analysis
        source_stats = await content_repo.get_source_analysis(start_date, end_date)

        # Get prompt generation efficiency by source
        prompt_efficiency = await prompt_repo.get_efficiency_by_source(
            start_date, end_date
        )

        return APIResponse.success(
            data={
                "period": f"{days} days",
                "source_statistics": source_stats,
                "prompt_efficiency": prompt_efficiency
            },
            message="Source analysis retrieved"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get source analysis"
        )


@router.get(
    "/reports/quality-report",
    response_model=Dict[str, Any],
    summary="Generate Quality Report",
    description="Generate comprehensive quality report"
)
async def generate_quality_report(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    include_details: bool = Query(False, description="Include detailed breakdowns"),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Generate comprehensive quality report."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Generate quality report
        quality_report = await prompt_repo.generate_quality_report(
            start_date, end_date, include_details
        )

        return APIResponse.success(
            data={
                "report_period": f"{days} days",
                "generated_at": end_date.isoformat(),
                **quality_report
            },
            message="Quality report generated"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate quality report"
        )


@router.get(
    "/system/health-metrics",
    response_model=Dict[str, Any],
    summary="Get System Health Metrics",
    description="Get system performance and health indicators"
)
async def get_system_health_metrics(
    content_repo: ContentRepository = Depends(get_content_repository),
    prompt_repo: PromptRepository = Depends(get_prompt_repository)
) -> Dict[str, Any]:
    """Get system health and performance metrics."""
    try:
        # Get system health indicators
        processing_queue_size = await content_repo.get_queue_size()
        failed_jobs_count = await content_repo.get_failed_jobs_count()
        avg_processing_time = await content_repo.get_avg_processing_time()

        # Calculate health score
        health_score = 100
        if processing_queue_size > 100:
            health_score -= 20
        if failed_jobs_count > 10:
            health_score -= 30
        if avg_processing_time > 300:  # 5 minutes
            health_score -= 25

        health_status = "healthy" if health_score >= 80 else "warning" if health_score >= 60 else "critical"

        return APIResponse.success(
            data={
                "health_score": health_score,
                "health_status": health_status,
                "metrics": {
                    "processing_queue_size": processing_queue_size,
                    "failed_jobs_count": failed_jobs_count,
                    "avg_processing_time_seconds": avg_processing_time
                },
                "recommendations": _get_health_recommendations(
                    processing_queue_size, failed_jobs_count, avg_processing_time
                )
            },
            message="System health metrics retrieved"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system health metrics"
        )


def _get_health_recommendations(queue_size: int, failed_jobs: int, avg_time: float) -> List[Dict[str, str]]:
    """Generate health recommendations based on metrics."""
    recommendations = []

    if queue_size > 100:
        recommendations.append({
            "type": "performance",
            "message": "High processing queue detected. Consider scaling workers.",
            "priority": "high"
        })

    if failed_jobs > 10:
        recommendations.append({
            "type": "reliability",
            "message": "High failure rate detected. Review error logs and retry logic.",
            "priority": "critical"
        })

    if avg_time > 300:
        recommendations.append({
            "type": "optimization",
            "message": "Slow processing times. Consider model optimization or caching.",
            "priority": "medium"
        })

    return recommendations