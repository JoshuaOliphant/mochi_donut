"""
Content processing tasks for the Mochi Donut system.

Handles async content extraction, vector embedding generation,
duplicate detection, and batch processing workflows.
"""

import asyncio
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, urlunparse
import aiohttp
from celery import Task
from celery.exceptions import Retry
import structlog

from app.tasks.celery_app import celery_app, TaskConfig
from app.services.jina_reader import JinaReaderService
from app.services.vector_store import VectorStoreService
from app.services.cache import CacheService
from app.repositories.content import ContentRepository
from app.db.session import get_async_session
from app.schemas.content import ContentCreate, ContentResponse

logger = structlog.get_logger()


class ContentProcessingTask(Task):
    """Base class for content processing tasks with common utilities."""

    def __init__(self):
        self.jina_service = JinaReaderService()
        self.vector_service = VectorStoreService()
        self.cache_service = CacheService()
        self.content_repo = ContentRepository()

    def normalize_url(self, url: str) -> str:
        """Normalize URL for consistent processing."""
        try:
            parsed = urlparse(url.strip().lower())
            # Remove fragment and common tracking parameters
            normalized = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path.rstrip('/'),
                parsed.params,
                parsed.query,  # TODO: Filter tracking params
                ''  # Remove fragment
            ))
            return normalized
        except Exception as e:
            logger.warning("Failed to normalize URL", url=url, error=str(e))
            return url

    def generate_content_hash(self, url: str, content: str = "") -> str:
        """Generate consistent hash for content deduplication."""
        normalized_url = self.normalize_url(url)
        hash_input = f"{normalized_url}:{content[:1000]}"  # Include first 1KB of content
        return hashlib.sha256(hash_input.encode()).hexdigest()

    async def check_duplicate(self, url: str, content_hash: str) -> Optional[Dict[str, Any]]:
        """Check for duplicate content using hash and semantic similarity."""
        try:
            async with get_async_session() as session:
                # Check URL hash first (fast)
                existing = await self.content_repo.find_by_hash(session, content_hash)
                if existing:
                    return {
                        "type": "exact_duplicate",
                        "existing_id": existing.id,
                        "confidence": 1.0
                    }

                # Check semantic similarity (slower but more thorough)
                if len(content_hash) > 100:  # Only for substantial content
                    similar_docs = await self.vector_service.search_similar(
                        query=content_hash[:500],  # Use beginning of content
                        threshold=0.85,
                        limit=3
                    )

                    if similar_docs:
                        return {
                            "type": "semantic_duplicate",
                            "similar_docs": similar_docs,
                            "confidence": similar_docs[0]["score"]
                        }

        except Exception as e:
            logger.warning("Duplicate check failed", url=url, error=str(e))

        return None


@celery_app.task(bind=True, base=ContentProcessingTask, **TaskConfig.get_retry_config("content"))
def process_url_content(self, url: str, user_id: Optional[str] = None, options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Process URL content through the complete pipeline.

    Args:
        url: Target URL to process
        user_id: Optional user identifier
        options: Processing options (force_refresh, skip_duplicates, etc.)

    Returns:
        Dict with processing results including content_id and status
    """
    task_logger = TaskConfig.get_task_logger("process_url_content")
    options = options or {}

    try:
        task_logger.info("Starting URL content processing", url=url, task_id=self.request.id)

        # Normalize URL
        normalized_url = self.normalize_url(url)

        # Check cache unless force refresh requested
        cache_key = f"content:processed:{hashlib.md5(normalized_url.encode()).hexdigest()}"

        if not options.get("force_refresh", False):
            cached_result = asyncio.run(self.cache_service.get(cache_key))
            if cached_result:
                task_logger.info("Returning cached result", url=url)
                return json.loads(cached_result)

        # Extract content using JinaAI
        extraction_result = extract_content_jina.delay(normalized_url, options)
        content_data = extraction_result.get(timeout=300)  # 5 minute timeout

        if not content_data.get("success"):
            raise Exception(f"Content extraction failed: {content_data.get('error')}")

        # Check for duplicates unless skipped
        duplicate_check = None
        if not options.get("skip_duplicates", False):
            content_hash = self.generate_content_hash(normalized_url, content_data["markdown_content"])
            duplicate_check = asyncio.run(self.check_duplicate(normalized_url, content_hash))

            if duplicate_check and not options.get("allow_duplicates", False):
                result = {
                    "success": True,
                    "duplicate": True,
                    "duplicate_info": duplicate_check,
                    "content_id": duplicate_check.get("existing_id"),
                }
                # Cache the duplicate result
                asyncio.run(self.cache_service.set(cache_key, json.dumps(result), ttl=3600))
                return result

        # Store content in database
        async def store_content():
            async with get_async_session() as session:
                content_create = ContentCreate(
                    source_url=normalized_url,
                    source_type="web",
                    raw_text=content_data.get("raw_text", ""),
                    markdown_content=content_data["markdown_content"],
                    metadata={
                        "title": content_data.get("title"),
                        "extraction_method": "jina_reader",
                        "processed_at": content_data.get("processed_at"),
                        "options": options,
                        "user_id": user_id,
                    },
                    hash=self.generate_content_hash(normalized_url, content_data["markdown_content"])
                )

                content = await self.content_repo.create(session, content_create)
                await session.commit()
                return content

        stored_content = asyncio.run(store_content())

        # Generate embeddings asynchronously
        embedding_task = generate_embeddings.delay(
            stored_content.id,
            content_data["markdown_content"],
            content_data.get("title", "")
        )

        result = {
            "success": True,
            "duplicate": False,
            "content_id": stored_content.id,
            "url": normalized_url,
            "title": content_data.get("title"),
            "content_length": len(content_data["markdown_content"]),
            "embedding_task_id": embedding_task.id,
            "processing_time": content_data.get("processing_time", 0),
        }

        # Cache successful result
        asyncio.run(self.cache_service.set(cache_key, json.dumps(result), ttl=3600))

        task_logger.info("URL content processing completed", content_id=stored_content.id, url=url)
        return result

    except Exception as e:
        task_logger.error("URL content processing failed", url=url, error=str(e))
        raise self.retry(countdown=60, max_retries=3, exc=e)


@celery_app.task(bind=True, **TaskConfig.get_retry_config("external_api"))
def extract_content_jina(self, url: str, options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Extract content from URL using JinaAI Reader API.

    Args:
        url: Target URL
        options: JinaAI options (use_readerlm, timeout, etc.)

    Returns:
        Dict with extracted content and metadata
    """
    task_logger = TaskConfig.get_task_logger("extract_content_jina")
    options = options or {}

    try:
        task_logger.info("Starting JinaAI content extraction", url=url, task_id=self.request.id)

        # Initialize JinaAI service if not already done
        if not hasattr(self, 'jina_service'):
            from app.services.jina_reader import JinaReaderService
            self.jina_service = JinaReaderService()

        # Extract content
        result = asyncio.run(self.jina_service.fetch_as_markdown(
            url=url,
            use_readerlm=options.get("use_readerlm", False),
            timeout=options.get("timeout", 30),
            include_links=options.get("include_links", True),
            include_images=options.get("include_images", False),
        ))

        if not result.get("success"):
            raise Exception(f"JinaAI extraction failed: {result.get('error')}")

        task_logger.info(
            "JinaAI content extraction completed",
            url=url,
            content_length=len(result.get("markdown_content", "")),
            processing_time=result.get("processing_time", 0)
        )

        return result

    except Exception as e:
        task_logger.error("JinaAI content extraction failed", url=url, error=str(e))
        raise self.retry(countdown=30, max_retries=5, exc=e)


@celery_app.task(bind=True, **TaskConfig.get_retry_config("content"))
def generate_embeddings(self, content_id: str, markdown_content: str, title: str = "") -> Dict[str, Any]:
    """
    Generate and store vector embeddings for content.

    Args:
        content_id: Content UUID
        markdown_content: Markdown text to embed
        title: Content title for metadata

    Returns:
        Dict with embedding results and chroma document ID
    """
    task_logger = TaskConfig.get_task_logger("generate_embeddings")

    try:
        task_logger.info("Starting embedding generation", content_id=content_id, task_id=self.request.id)

        # Initialize vector store if not already done
        if not hasattr(self, 'vector_service'):
            from app.services.vector_store import VectorStoreService
            self.vector_service = VectorStoreService()

        # Prepare document for embedding
        doc_metadata = {
            "content_id": content_id,
            "title": title,
            "content_length": len(markdown_content),
            "type": "markdown",
        }

        # Add to vector store
        chroma_result = asyncio.run(self.vector_service.add_document(
            content_id=content_id,
            text=markdown_content,
            metadata=doc_metadata
        ))

        if not chroma_result.get("success"):
            raise Exception(f"Vector storage failed: {chroma_result.get('error')}")

        # Update content record with chroma_id
        async def update_content():
            async with get_async_session() as session:
                await self.content_repo.update(
                    session,
                    content_id,
                    {"chroma_id": chroma_result["document_id"]}
                )
                await session.commit()

        asyncio.run(update_content())

        result = {
            "success": True,
            "content_id": content_id,
            "chroma_id": chroma_result["document_id"],
            "embedding_dimensions": chroma_result.get("dimensions", 0),
            "processing_time": chroma_result.get("processing_time", 0),
        }

        task_logger.info("Embedding generation completed", content_id=content_id, chroma_id=result["chroma_id"])
        return result

    except Exception as e:
        task_logger.error("Embedding generation failed", content_id=content_id, error=str(e))
        raise self.retry(countdown=60, max_retries=2, exc=e)


@celery_app.task(bind=True, **TaskConfig.get_retry_config("content"))
def detect_duplicates(self, content_ids: List[str], similarity_threshold: float = 0.85) -> Dict[str, Any]:
    """
    Detect duplicate content across multiple items using semantic similarity.

    Args:
        content_ids: List of content IDs to check
        similarity_threshold: Minimum similarity score for duplicates

    Returns:
        Dict with duplicate groups and similarity scores
    """
    task_logger = TaskConfig.get_task_logger("detect_duplicates")

    try:
        task_logger.info("Starting duplicate detection", content_count=len(content_ids), task_id=self.request.id)

        # Initialize services
        if not hasattr(self, 'vector_service'):
            from app.services.vector_store import VectorStoreService
            self.vector_service = VectorStoreService()

        duplicate_groups = []
        processed_ids = set()

        for content_id in content_ids:
            if content_id in processed_ids:
                continue

            # Find similar content
            similar_docs = asyncio.run(self.vector_service.search_similar_by_id(
                content_id=content_id,
                threshold=similarity_threshold,
                limit=10
            ))

            if len(similar_docs) > 1:  # Found duplicates
                group = {
                    "primary_id": content_id,
                    "duplicates": [],
                    "max_similarity": 0.0,
                }

                for doc in similar_docs[1:]:  # Skip self
                    if doc["content_id"] not in processed_ids:
                        group["duplicates"].append({
                            "content_id": doc["content_id"],
                            "similarity_score": doc["score"],
                        })
                        group["max_similarity"] = max(group["max_similarity"], doc["score"])
                        processed_ids.add(doc["content_id"])

                if group["duplicates"]:
                    duplicate_groups.append(group)
                    processed_ids.add(content_id)

        result = {
            "success": True,
            "total_checked": len(content_ids),
            "duplicate_groups": duplicate_groups,
            "total_duplicates": sum(len(group["duplicates"]) for group in duplicate_groups),
            "similarity_threshold": similarity_threshold,
        }

        task_logger.info(
            "Duplicate detection completed",
            total_groups=len(duplicate_groups),
            total_duplicates=result["total_duplicates"]
        )

        return result

    except Exception as e:
        task_logger.error("Duplicate detection failed", error=str(e))
        raise self.retry(countdown=120, max_retries=2, exc=e)


@celery_app.task(bind=True, **TaskConfig.get_retry_config("content"))
def batch_process_content(self, urls: List[str], batch_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Process multiple URLs in batch with progress tracking.

    Args:
        urls: List of URLs to process
        batch_options: Batch processing options

    Returns:
        Dict with batch processing results and progress
    """
    task_logger = TaskConfig.get_task_logger("batch_process_content")
    batch_options = batch_options or {}

    try:
        task_logger.info("Starting batch content processing", url_count=len(urls), task_id=self.request.id)

        # Initialize progress tracking
        batch_id = self.request.id
        cache_key = f"batch:progress:{batch_id}"

        async def update_progress(processed: int, total: int, current_url: str = ""):
            progress_data = {
                "batch_id": batch_id,
                "processed": processed,
                "total": total,
                "progress_percent": (processed / total) * 100 if total > 0 else 0,
                "current_url": current_url,
                "status": "processing" if processed < total else "completed",
            }
            await self.cache_service.set(cache_key, json.dumps(progress_data), ttl=3600)

        # Process URLs in batches
        batch_size = batch_options.get("batch_size", 5)
        concurrent_limit = batch_options.get("concurrent_limit", 3)
        results = []
        failed_urls = []

        asyncio.run(update_progress(0, len(urls)))

        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i:i + batch_size]
            batch_tasks = []

            for url in batch_urls:
                # Submit individual processing task
                task = process_url_content.delay(
                    url=url,
                    user_id=batch_options.get("user_id"),
                    options={
                        **batch_options.get("processing_options", {}),
                        "batch_id": batch_id,
                    }
                )
                batch_tasks.append((url, task))

            # Wait for batch completion with timeout
            timeout = batch_options.get("task_timeout", 300)  # 5 minutes per task

            for url, task in batch_tasks:
                try:
                    asyncio.run(update_progress(len(results), len(urls), url))

                    result = task.get(timeout=timeout)
                    result["url"] = url
                    results.append(result)

                except Exception as e:
                    task_logger.warning("Batch item failed", url=url, error=str(e))
                    failed_urls.append({"url": url, "error": str(e)})

                # Update progress
                asyncio.run(update_progress(len(results) + len(failed_urls), len(urls)))

        # Final result summary
        successful_results = [r for r in results if r.get("success")]
        duplicate_results = [r for r in successful_results if r.get("duplicate")]

        summary = {
            "success": True,
            "batch_id": batch_id,
            "total_urls": len(urls),
            "successful": len(successful_results),
            "failed": len(failed_urls),
            "duplicates": len(duplicate_results),
            "new_content": len(successful_results) - len(duplicate_results),
            "results": results,
            "failed_urls": failed_urls,
        }

        # Run duplicate detection on new content if requested
        if batch_options.get("detect_duplicates", True) and len(successful_results) > 1:
            new_content_ids = [r["content_id"] for r in successful_results if not r.get("duplicate")]
            if len(new_content_ids) > 1:
                duplicate_task = detect_duplicates.delay(new_content_ids)
                summary["duplicate_detection_task_id"] = duplicate_task.id

        asyncio.run(update_progress(len(urls), len(urls)))

        task_logger.info(
            "Batch content processing completed",
            batch_id=batch_id,
            successful=len(successful_results),
            failed=len(failed_urls)
        )

        return summary

    except Exception as e:
        task_logger.error("Batch content processing failed", error=str(e))
        raise self.retry(countdown=120, max_retries=1, exc=e)


@celery_app.task(bind=True, **TaskConfig.get_retry_config("maintenance"))
def cleanup_failed_extractions(self, max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Clean up failed content extraction attempts.

    Args:
        max_age_hours: Maximum age of failed attempts to keep

    Returns:
        Dict with cleanup results
    """
    task_logger = TaskConfig.get_task_logger("cleanup_failed_extractions")

    try:
        task_logger.info("Starting failed extraction cleanup", max_age_hours=max_age_hours)

        # This would typically clean up partial records, temp files, etc.
        # Implementation depends on specific error tracking strategy

        result = {
            "success": True,
            "cleaned_records": 0,
            "cleaned_cache_entries": 0,
            "max_age_hours": max_age_hours,
        }

        task_logger.info("Failed extraction cleanup completed", **result)
        return result

    except Exception as e:
        task_logger.error("Failed extraction cleanup error", error=str(e))
        raise self.retry(countdown=300, max_retries=1, exc=e)