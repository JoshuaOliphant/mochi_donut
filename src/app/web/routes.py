"""
Web interface routes for Mochi Donut.

This module provides FastAPI routes for the web interface, supporting both
full page loads and HTMX partial updates for progressive enhancement.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.database import get_db
from src.app.schemas.content import ContentCreate
from src.app.schemas.prompt import PromptUpdate
from src.app.repositories.content import ContentRepository
from src.app.repositories.prompt import PromptRepository
from src.app.services.content_processor import ContentProcessor

# Setup logging
logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="src/app/web/templates")

# Create router
web_router = APIRouter(prefix="/web", tags=["web"])


class WebHelpers:
    """Helper functions for web interface."""

    @staticmethod
    def is_htmx_request(request: Request) -> bool:
        """Check if request is from HTMX."""
        return request.headers.get("HX-Request") == "true"

    @staticmethod
    def get_base_template(request: Request) -> str:
        """Get appropriate base template based on request type."""
        if WebHelpers.is_htmx_request(request):
            return "components/base_partial.html"
        return "base.html"

    @staticmethod
    def add_flash_message(request: Request, message: str, category: str = "info"):
        """Add flash message to session."""
        if not hasattr(request.state, "flash_messages"):
            request.state.flash_messages = []
        request.state.flash_messages.append({
            "text": message,
            "category": category
        })

    @staticmethod
    def get_flash_messages(request: Request) -> List[Dict[str, str]]:
        """Get and clear flash messages from session."""
        messages = getattr(request.state, "flash_messages", [])
        request.state.flash_messages = []
        return messages


@web_router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Home page with content submission form and dashboard."""
    try:
        # Get dashboard statistics
        content_repo = ContentRepository(db)
        prompt_repo = PromptRepository(db)

        # Calculate stats
        total_content = await content_repo.count()
        total_prompts = await prompt_repo.count()
        pending_review = await prompt_repo.count_by_status("pending")

        # Get average quality score
        avg_quality = await prompt_repo.get_average_quality()

        stats = {
            "total_content": total_content,
            "total_prompts": total_prompts,
            "pending_review": pending_review,
            "avg_quality": avg_quality or 0.75
        }

        # Get recent activity (mock data for now)
        recent_activity = [
            {
                "type": "content_processed",
                "description": "Processed article: 'Understanding Machine Learning'",
                "timestamp": datetime.now() - timedelta(hours=2)
            },
            {
                "type": "prompts_generated",
                "description": "Generated 8 prompts with 87% average quality",
                "timestamp": datetime.now() - timedelta(hours=4)
            }
        ]

        context = {
            "request": request,
            "stats": stats,
            "recent_activity": recent_activity,
            "messages": WebHelpers.get_flash_messages(request)
        }

        return templates.TemplateResponse("pages/index.html", context)

    except Exception as e:
        logger.error(f"Error loading home page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@web_router.get("/review", response_class=HTMLResponse)
async def review_prompts(
    request: Request,
    page: int = 1,
    status: Optional[str] = None,
    quality: Optional[str] = None,
    content_type: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "created_desc",
    db: AsyncSession = Depends(get_db)
):
    """Review prompts page with filtering and pagination."""
    try:
        prompt_repo = PromptRepository(db)

        # Build filters
        filters = {
            "status": status,
            "quality": quality,
            "content_type": content_type,
            "search": search,
            "sort": sort
        }

        # Get prompts with pagination
        prompts, total = await prompt_repo.get_paginated(
            page=page,
            per_page=10,
            filters=filters
        )

        # Create pagination object
        page_obj = {
            "current_page": page,
            "total_pages": (total + 9) // 10,  # Ceiling division
            "total_items": total,
            "has_prev": page > 1,
            "has_next": page < (total + 9) // 10,
            "prev_page": page - 1 if page > 1 else None,
            "next_page": page + 1 if page < (total + 9) // 10 else None,
            "start_index": (page - 1) * 10 + 1,
            "end_index": min(page * 10, total),
            "page_range": _get_page_range(page, (total + 9) // 10)
        }

        # Get summary stats
        summary = await prompt_repo.get_summary_stats()

        context = {
            "request": request,
            "prompts": prompts,
            "page_obj": page_obj,
            "filters": filters,
            "summary": summary,
            "messages": WebHelpers.get_flash_messages(request)
        }

        template_name = "pages/review.html"
        if WebHelpers.is_htmx_request(request):
            template_name = "components/prompt_list.html"

        return templates.TemplateResponse(template_name, context)

    except Exception as e:
        logger.error(f"Error loading review page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@web_router.get("/analytics", response_class=HTMLResponse)
async def analytics(
    request: Request,
    period: str = "30d",
    db: AsyncSession = Depends(get_db)
):
    """Analytics dashboard with metrics and charts."""
    try:
        # Calculate date range based on period
        end_date = datetime.now()
        if period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)

        content_repo = ContentRepository(db)
        prompt_repo = PromptRepository(db)

        # Get key metrics
        metrics = await _get_analytics_metrics(
            content_repo, prompt_repo, start_date, end_date
        )

        # Get chart data
        quality_data = await _get_quality_trend_data(
            prompt_repo, start_date, end_date
        )
        volume_data = await _get_volume_data(
            content_repo, start_date, end_date
        )

        # Get breakdowns
        content_types = await _get_content_type_breakdown(
            content_repo, start_date, end_date
        )
        quality_distribution = await _get_quality_distribution(
            prompt_repo, start_date, end_date
        )

        # Mock cost and agent performance data
        cost_breakdown = _get_mock_cost_breakdown()
        agent_performance = _get_mock_agent_performance()

        context = {
            "request": request,
            "period": period,
            "metrics": metrics,
            "quality_data": quality_data,
            "volume_data": volume_data,
            "content_types": content_types,
            "quality_distribution": quality_distribution,
            "cost_breakdown": cost_breakdown,
            "agent_performance": agent_performance,
            "messages": WebHelpers.get_flash_messages(request)
        }

        template_name = "pages/analytics.html"
        if WebHelpers.is_htmx_request(request):
            template_name = "components/analytics_content.html"

        return templates.TemplateResponse(template_name, context)

    except Exception as e:
        logger.error(f"Error loading analytics page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@web_router.get("/settings", response_class=HTMLResponse)
async def settings(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Settings page for configuration."""
    try:
        # Load current settings (mock for now)
        settings = {
            "mochi_api_key": "****",
            "mochi_deck_id": "",
            "openai_api_key": "****",
            "openai_organization": "",
            "jina_api_key": "",
            "content_analysis_model": "gpt-5-nano",
            "prompt_generation_model": "gpt-5-mini",
            "quality_review_model": "gpt-5-standard",
            "minimum_quality_score": 0.6,
            "auto_approve_threshold": 0.85,
            "auto_create_mochi_cards": False,
            "enable_refinement": True,
            "parallel_processing": False
        }

        # System information
        system_info = {
            "version": "1.0.0",
            "redis_connected": True,
            "last_backup": datetime.now() - timedelta(days=1)
        }

        context = {
            "request": request,
            "settings": settings,
            "system_info": system_info,
            "messages": WebHelpers.get_flash_messages(request)
        }

        return templates.TemplateResponse("pages/settings.html", context)

    except Exception as e:
        logger.error(f"Error loading settings page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@web_router.post("/content/process")
async def process_content(
    request: Request,
    url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    target_concepts: int = Form(10),
    difficulty_level: str = Form("intermediate"),
    db: AsyncSession = Depends(get_db)
):
    """Process new content and generate prompts."""
    try:
        if not url and not file:
            WebHelpers.add_flash_message(
                request, "Please provide either a URL or upload a file", "error"
            )
            return templates.TemplateResponse(
                "components/processing_status.html",
                {"request": request, "error": "No content provided"}
            )

        # Initialize content processor
        content_processor = ContentProcessor(db)

        if url:
            # Process URL
            content_data = ContentCreate(
                url=url,
                content_type="url",
                target_concepts=target_concepts,
                difficulty_level=difficulty_level
            )

            # Start background processing
            processing_id = await content_processor.process_url_async(content_data)

        else:
            # Process file upload
            file_content = await file.read()
            content_data = ContentCreate(
                title=file.filename,
                content_type=_get_file_type(file.filename),
                raw_content=file_content.decode("utf-8"),
                target_concepts=target_concepts,
                difficulty_level=difficulty_level
            )

            # Start background processing
            processing_id = await content_processor.process_content_async(content_data)

        # Return processing status component
        context = {
            "request": request,
            "processing_id": processing_id,
            "status": "started",
            "message": "Content processing started. You will be notified when complete."
        }

        WebHelpers.add_flash_message(
            request, "Content processing started successfully", "success"
        )

        return templates.TemplateResponse(
            "components/processing_status.html", context
        )

    except Exception as e:
        logger.error(f"Error processing content: {e}")
        WebHelpers.add_flash_message(
            request, f"Error processing content: {str(e)}", "error"
        )
        return templates.TemplateResponse(
            "components/processing_status.html",
            {"request": request, "error": str(e)}
        )


@web_router.post("/prompts/{prompt_id}/approve")
async def approve_prompt(
    request: Request,
    prompt_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Approve a prompt."""
    try:
        prompt_repo = PromptRepository(db)

        # Update prompt status
        prompt = await prompt_repo.update(
            prompt_id,
            PromptUpdate(status="approved")
        )

        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")

        WebHelpers.add_flash_message(
            request, "Prompt approved successfully", "success"
        )

        # Return updated prompt card
        context = {
            "request": request,
            "prompt": prompt
        }

        return templates.TemplateResponse(
            "components/prompt_card.html", context
        )

    except Exception as e:
        logger.error(f"Error approving prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@web_router.post("/prompts/{prompt_id}/reject")
async def reject_prompt(
    request: Request,
    prompt_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Reject a prompt."""
    try:
        prompt_repo = PromptRepository(db)

        # Update prompt status
        prompt = await prompt_repo.update(
            prompt_id,
            PromptUpdate(status="rejected")
        )

        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")

        WebHelpers.add_flash_message(
            request, "Prompt rejected", "info"
        )

        # Return updated prompt card
        context = {
            "request": request,
            "prompt": prompt
        }

        return templates.TemplateResponse(
            "components/prompt_card.html", context
        )

    except Exception as e:
        logger.error(f"Error rejecting prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Helper functions

def _get_page_range(current_page: int, total_pages: int, delta: int = 2) -> List:
    """Generate page range for pagination with ellipsis."""
    if total_pages <= 7:
        return list(range(1, total_pages + 1))

    pages = []

    # Always show first page
    pages.append(1)

    # Add ellipsis if needed
    if current_page > delta + 2:
        pages.append("...")

    # Add pages around current
    start = max(2, current_page - delta)
    end = min(total_pages, current_page + delta + 1)
    pages.extend(range(start, end))

    # Add ellipsis if needed
    if current_page < total_pages - delta - 1:
        pages.append("...")

    # Always show last page
    if total_pages > 1:
        pages.append(total_pages)

    return pages


def _get_file_type(filename: str) -> str:
    """Determine file type from filename."""
    if filename.lower().endswith('.pdf'):
        return 'pdf'
    elif filename.lower().endswith(('.txt', '.md')):
        return 'text'
    elif filename.lower().endswith('.docx'):
        return 'document'
    else:
        return 'unknown'


async def _get_analytics_metrics(
    content_repo: ContentRepository,
    prompt_repo: PromptRepository,
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """Get key analytics metrics for the period."""
    # Implementation would use actual repository methods
    return {
        "content_processed": 25,
        "content_change": 15.2,
        "prompts_generated": 180,
        "prompts_change": 22.1,
        "avg_quality": 0.82,
        "quality_change": 0.05,
        "total_cost": 12.45,
        "cost_change": -8.3
    }


async def _get_quality_trend_data(
    prompt_repo: PromptRepository,
    start_date: datetime,
    end_date: datetime
) -> List[Dict[str, Any]]:
    """Get quality trend data for charts."""
    # Mock data - implementation would query database
    return [
        {"date": start_date + timedelta(days=i), "avg_quality": 0.75 + (i * 0.02)}
        for i in range((end_date - start_date).days)
    ]


async def _get_volume_data(
    content_repo: ContentRepository,
    start_date: datetime,
    end_date: datetime
) -> List[Dict[str, Any]]:
    """Get processing volume data for charts."""
    # Mock data
    import random
    return [
        {"date": start_date + timedelta(days=i), "count": random.randint(1, 10)}
        for i in range((end_date - start_date).days)
    ]


async def _get_content_type_breakdown(
    content_repo: ContentRepository,
    start_date: datetime,
    end_date: datetime
) -> List[Dict[str, Any]]:
    """Get content type breakdown."""
    return [
        {"type": "article", "count": 15, "percentage": 60},
        {"type": "pdf", "count": 7, "percentage": 28},
        {"type": "text", "count": 3, "percentage": 12}
    ]


async def _get_quality_distribution(
    prompt_repo: PromptRepository,
    start_date: datetime,
    end_date: datetime
) -> List[Dict[str, Any]]:
    """Get quality score distribution."""
    return [
        {"label": "Excellent", "count": 75, "percentage": 42},
        {"label": "Good", "count": 60, "percentage": 33},
        {"label": "Fair", "count": 35, "percentage": 19},
        {"label": "Poor", "count": 10, "percentage": 6}
    ]


def _get_mock_cost_breakdown() -> List[Dict[str, Any]]:
    """Get mock cost breakdown data."""
    return [
        {
            "model_name": "GPT-5 Nano",
            "requests": 1250,
            "tokens": 125000,
            "cost": 6.25,
            "percentage": 50.2
        },
        {
            "model_name": "GPT-5 Mini",
            "requests": 180,
            "tokens": 45000,
            "cost": 4.50,
            "percentage": 36.1
        },
        {
            "model_name": "GPT-5 Standard",
            "requests": 25,
            "tokens": 12500,
            "cost": 1.70,
            "percentage": 13.7
        }
    ]


def _get_mock_agent_performance() -> List[Dict[str, Any]]:
    """Get mock agent performance data."""
    return [
        {
            "name": "Content Analyzer",
            "success_rate": 0.96,
            "avg_time": 2.3
        },
        {
            "name": "Prompt Generator",
            "success_rate": 0.91,
            "avg_time": 4.7
        },
        {
            "name": "Quality Reviewer",
            "success_rate": 0.94,
            "avg_time": 3.1
        },
        {
            "name": "Refinement Agent",
            "success_rate": 0.88,
            "avg_time": 5.2
        }
    ]