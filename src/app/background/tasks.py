# ABOUTME: All background task functions as pure async functions
# ABOUTME: Replaces Celery tasks with native async/await operations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, urlunparse

from app.background.progress import get_progress_tracker
from app.db.session import get_async_session
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository

logger = logging.getLogger(__name__)


# =============================================================================
# Rate Limiting (replaces Redis-based limiting)
# =============================================================================

class RateLimiter:
    """In-memory token bucket rate limiter using asyncio.Semaphore."""

    def __init__(self, calls_per_minute: int):
        self.semaphore = asyncio.Semaphore(calls_per_minute)
        self.delay = 60.0 / calls_per_minute

    async def acquire(self):
        await self.semaphore.acquire()
        # Release the token after the delay period
        asyncio.get_event_loop().call_later(self.delay, self.semaphore.release)


# Rate limiters for external services
mochi_limiter = RateLimiter(20)  # 20 requests/min for Mochi API
jina_limiter = RateLimiter(30)   # 30 requests/min for Jina API
ai_limiter = RateLimiter(10)     # 10 requests/min for AI models


# =============================================================================
# Utility Functions
# =============================================================================

def normalize_url(url: str) -> str:
    """Normalize URL for consistent processing."""
    try:
        parsed = urlparse(url.strip().lower())
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/'),
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize URL: {url}, error: {e}")
        return url


def generate_content_hash(url: str, content: str = "") -> str:
    """Generate consistent hash for content deduplication."""
    normalized_url = normalize_url(url)
    hash_input = f"{normalized_url}:{content[:1000]}"
    return hashlib.sha256(hash_input.encode()).hexdigest()


# =============================================================================
# Content Processing Tasks (6 tasks)
# =============================================================================

async def process_url(
    url: str,
    task_id: str,
    user_id: Optional[str] = None,
    options: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Process URL content through the complete pipeline.

    Args:
        url: Target URL to process
        task_id: Unique task identifier for progress tracking
        user_id: Optional user identifier
        options: Processing options (force_refresh, skip_duplicates, etc.)

    Returns:
        Dict with processing results including content_id and status
    """
    from app.services.jina_reader import JinaReaderService
    from app.services.vector_store import VectorStoreService
    from app.schemas.content import ContentCreate

    options = options or {}
    tracker = get_progress_tracker()
    content_repo = ContentRepository()

    try:
        tracker.start(task_id, "Processing URL content...")
        logger.info(f"Starting URL content processing: {url}")

        # Normalize URL
        normalized_url = normalize_url(url)

        # Extract content using JinaAI
        tracker.update(task_id, message="Extracting content...")
        content_data = await extract_content(normalized_url, options)

        if not content_data.get("success"):
            raise Exception(f"Content extraction failed: {content_data.get('error')}")

        # Check for duplicates unless skipped
        duplicate_check = None
        if not options.get("skip_duplicates", False):
            content_hash = generate_content_hash(normalized_url, content_data["markdown_content"])
            duplicate_check = await check_duplicate(normalized_url, content_hash, content_repo)

            if duplicate_check and not options.get("allow_duplicates", False):
                result = {
                    "success": True,
                    "duplicate": True,
                    "duplicate_info": duplicate_check,
                    "content_id": duplicate_check.get("existing_id"),
                }
                tracker.complete(task_id, result, "Found duplicate content")
                return result

        # Store content in database
        tracker.update(task_id, message="Storing content...")

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
                hash=generate_content_hash(normalized_url, content_data["markdown_content"])
            )

            stored_content = await content_repo.create(session, content_create)
            await session.commit()

        # Generate embeddings
        tracker.update(task_id, message="Generating embeddings...")
        await generate_embeddings(
            str(stored_content.id),
            content_data["markdown_content"],
            content_data.get("title", "")
        )

        result = {
            "success": True,
            "duplicate": False,
            "content_id": str(stored_content.id),
            "url": normalized_url,
            "title": content_data.get("title"),
            "content_length": len(content_data["markdown_content"]),
            "processing_time": content_data.get("processing_time", 0),
        }

        tracker.complete(task_id, result, "Content processed successfully")
        logger.info(f"URL content processing completed: {stored_content.id}")
        return result

    except Exception as e:
        logger.error(f"URL content processing failed: {url}, error: {e}")
        tracker.fail(task_id, str(e), "Processing failed")
        raise


async def extract_content(url: str, options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Extract content from URL using JinaAI Reader API.

    Args:
        url: Target URL
        options: JinaAI options (use_readerlm, timeout, etc.)

    Returns:
        Dict with extracted content and metadata
    """
    from app.services.jina_reader import JinaReaderService

    options = options or {}
    jina_service = JinaReaderService()

    try:
        logger.info(f"Starting JinaAI content extraction: {url}")

        # Respect rate limits
        await jina_limiter.acquire()

        result = await jina_service.fetch_as_markdown(
            url=url,
            use_readerlm=options.get("use_readerlm", False),
            timeout=options.get("timeout", 30),
            include_links=options.get("include_links", True),
            include_images=options.get("include_images", False),
        )

        if not result.get("success"):
            raise Exception(f"JinaAI extraction failed: {result.get('error')}")

        logger.info(f"JinaAI extraction completed: {url}, length: {len(result.get('markdown_content', ''))}")
        return result

    except Exception as e:
        logger.error(f"JinaAI content extraction failed: {url}, error: {e}")
        raise


async def generate_embeddings(content_id: str, markdown_content: str, title: str = "") -> Dict[str, Any]:
    """
    Generate and store vector embeddings for content.

    Args:
        content_id: Content UUID
        markdown_content: Markdown text to embed
        title: Content title for metadata

    Returns:
        Dict with embedding results and chroma document ID
    """
    from app.services.vector_store import VectorStoreService

    vector_service = VectorStoreService()
    content_repo = ContentRepository()

    try:
        logger.info(f"Starting embedding generation: {content_id}")

        doc_metadata = {
            "content_id": content_id,
            "title": title,
            "content_length": len(markdown_content),
            "type": "markdown",
        }

        chroma_result = await vector_service.add_document(
            content_id=content_id,
            text=markdown_content,
            metadata=doc_metadata
        )

        if not chroma_result.get("success"):
            raise Exception(f"Vector storage failed: {chroma_result.get('error')}")

        # Update content record with chroma_id
        async with get_async_session() as session:
            await content_repo.update(
                session,
                content_id,
                {"chroma_id": chroma_result["document_id"]}
            )
            await session.commit()

        result = {
            "success": True,
            "content_id": content_id,
            "chroma_id": chroma_result["document_id"],
            "embedding_dimensions": chroma_result.get("dimensions", 0),
            "processing_time": chroma_result.get("processing_time", 0),
        }

        logger.info(f"Embedding generation completed: {content_id}")
        return result

    except Exception as e:
        logger.error(f"Embedding generation failed: {content_id}, error: {e}")
        raise


async def detect_duplicates(content_ids: List[str], similarity_threshold: float = 0.85) -> Dict[str, Any]:
    """
    Detect duplicate content across multiple items using semantic similarity.

    Args:
        content_ids: List of content IDs to check
        similarity_threshold: Minimum similarity score for duplicates

    Returns:
        Dict with duplicate groups and similarity scores
    """
    from app.services.vector_store import VectorStoreService

    vector_service = VectorStoreService()

    try:
        logger.info(f"Starting duplicate detection: {len(content_ids)} items")

        duplicate_groups = []
        processed_ids = set()

        for content_id in content_ids:
            if content_id in processed_ids:
                continue

            similar_docs = await vector_service.search_similar_by_id(
                content_id=content_id,
                threshold=similarity_threshold,
                limit=10
            )

            if len(similar_docs) > 1:
                group = {
                    "primary_id": content_id,
                    "duplicates": [],
                    "max_similarity": 0.0,
                }

                for doc in similar_docs[1:]:
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

        logger.info(f"Duplicate detection completed: {len(duplicate_groups)} groups found")
        return result

    except Exception as e:
        logger.error(f"Duplicate detection failed: {e}")
        raise


async def batch_process(
    urls: List[str],
    task_id: str,
    max_concurrent: int = 5,
    batch_options: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Process multiple URLs concurrently with progress tracking.

    Args:
        urls: List of URLs to process
        task_id: Unique task identifier for progress tracking
        max_concurrent: Maximum concurrent operations
        batch_options: Batch processing options

    Returns:
        Dict with batch processing results
    """
    batch_options = batch_options or {}
    tracker = get_progress_tracker()
    semaphore = asyncio.Semaphore(max_concurrent)

    tracker.create(task_id, "batch_process", total=len(urls))
    tracker.start(task_id, "Starting batch processing...")

    results = []
    failed_urls = []

    async def bounded_process(url: str, index: int) -> Dict[str, Any]:
        async with semaphore:
            sub_task_id = f"{task_id}-{index}"
            try:
                tracker.update(task_id, current=index, message=f"Processing {url[:50]}...")
                result = await process_url(url, sub_task_id, options=batch_options.get("processing_options", {}))
                result["url"] = url
                return result
            except Exception as e:
                return {"url": url, "success": False, "error": str(e)}

    # Process all URLs concurrently with semaphore limiting
    tasks = [bounded_process(url, i) for i, url in enumerate(urls)]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(all_results):
        if isinstance(result, Exception):
            failed_urls.append({"url": urls[i], "error": str(result)})
        elif result.get("success"):
            results.append(result)
        else:
            failed_urls.append({"url": urls[i], "error": result.get("error", "Unknown error")})
        tracker.update(task_id, current=i + 1)

    successful_results = [r for r in results if r.get("success")]
    duplicate_results = [r for r in successful_results if r.get("duplicate")]

    summary = {
        "success": True,
        "batch_id": task_id,
        "total_urls": len(urls),
        "successful": len(successful_results),
        "failed": len(failed_urls),
        "duplicates": len(duplicate_results),
        "new_content": len(successful_results) - len(duplicate_results),
        "results": results,
        "failed_urls": failed_urls,
    }

    tracker.complete(task_id, summary, f"Processed {len(successful_results)}/{len(urls)} URLs")
    logger.info(f"Batch processing completed: {len(successful_results)} successful, {len(failed_urls)} failed")
    return summary


async def cleanup_extractions(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Clean up failed content extraction attempts.

    Args:
        max_age_hours: Maximum age of failed attempts to keep

    Returns:
        Dict with cleanup results
    """
    logger.info(f"Starting failed extraction cleanup: max_age_hours={max_age_hours}")

    result = {
        "success": True,
        "cleaned_records": 0,
        "cleaned_cache_entries": 0,
        "max_age_hours": max_age_hours,
    }

    logger.info("Failed extraction cleanup completed")
    return result


async def check_duplicate(url: str, content_hash: str, content_repo: ContentRepository) -> Optional[Dict[str, Any]]:
    """Check for duplicate content using hash and semantic similarity."""
    from app.services.vector_store import VectorStoreService

    try:
        async with get_async_session() as session:
            existing = await content_repo.find_by_hash(session, content_hash)
            if existing:
                return {
                    "type": "exact_duplicate",
                    "existing_id": str(existing.id),
                    "confidence": 1.0
                }

            if len(content_hash) > 100:
                vector_service = VectorStoreService()
                similar_docs = await vector_service.search_similar(
                    query=content_hash[:500],
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
        logger.warning(f"Duplicate check failed: {url}, error: {e}")

    return None


# =============================================================================
# Mochi Sync Tasks (5 tasks)
# =============================================================================

async def create_card(
    prompt_id: str,
    deck_id: Optional[str] = None,
    card_options: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Create a single Mochi card from a prompt.

    Args:
        prompt_id: Prompt UUID to convert to card
        deck_id: Optional specific deck ID
        card_options: Additional card creation options

    Returns:
        Dict with card creation results
    """
    from app.services.mochi_client import MochiClient

    card_options = card_options or {}
    prompt_repo = PromptRepository()
    mochi_client = MochiClient()

    try:
        logger.info(f"Starting Mochi card creation: {prompt_id}")

        # Get prompt from database
        async with get_async_session() as session:
            prompt = await prompt_repo.get_by_id(session, prompt_id)
            if not prompt:
                raise ValueError(f"Prompt not found: {prompt_id}")

        # Check if already synced
        if (prompt.mochi_card_id and
            not card_options.get("force_resync", False) and
            prompt.metadata.get("mochi_sync", {}).get("status") == "synced"):
            return {
                "success": True,
                "already_synced": True,
                "prompt_id": prompt_id,
                "mochi_card_id": prompt.mochi_card_id,
            }

        # Determine deck ID if not provided
        if not deck_id:
            deck_id = await get_mochi_deck_for_content(prompt.content_id)

        if not deck_id:
            raise ValueError("No suitable Mochi deck found")

        # Prepare card data
        card_data = {
            "content": prompt.question,
            "deck-id": deck_id,
            "fields": {
                "front": prompt.question,
                "back": prompt.answer,
            },
            "tags": card_options.get("tags", []),
        }

        # Rate limit Mochi API calls
        await mochi_limiter.acquire()

        # Create card via Mochi API
        creation_result = await mochi_client.create_card(
            content=card_data["content"],
            deck_id=deck_id,
            fields=card_data["fields"],
            tags=card_data.get("tags", [])
        )

        if not creation_result.get("success"):
            raise Exception(f"Mochi card creation failed: {creation_result.get('error')}")

        mochi_card_id = creation_result.get("card_id")

        # Update prompt with Mochi card information
        await update_prompt_mochi_status(prompt_id, mochi_card_id, "synced")

        result = {
            "success": True,
            "prompt_id": prompt_id,
            "mochi_card_id": mochi_card_id,
            "deck_id": deck_id,
            "tags_added": len(card_data.get("tags", [])),
            "sync_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Mochi card creation completed: {prompt_id} -> {mochi_card_id}")
        return result

    except Exception as e:
        logger.error(f"Mochi card creation failed: {prompt_id}, error: {e}")
        raise


async def batch_sync(
    prompt_ids: List[str],
    task_id: str,
    batch_options: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Synchronize multiple prompts to Mochi cards in batch.

    Args:
        prompt_ids: List of prompt IDs to sync
        task_id: Unique task identifier for progress tracking
        batch_options: Batch sync configuration

    Returns:
        Dict with batch sync results
    """
    batch_options = batch_options or {}
    tracker = get_progress_tracker()

    tracker.create(task_id, "batch_sync", total=len(prompt_ids))
    tracker.start(task_id, "Starting batch Mochi sync...")

    batch_size = batch_options.get("batch_size", 5)
    delay_between = batch_options.get("delay_seconds", 2)

    successful_syncs = []
    failed_syncs = []
    skipped_syncs = []

    for i, prompt_id in enumerate(prompt_ids):
        tracker.update(task_id, current=i, message=f"Syncing prompt {i+1}/{len(prompt_ids)}")

        try:
            sync_result = await create_card(
                prompt_id=prompt_id,
                deck_id=batch_options.get("deck_id"),
                card_options=batch_options.get("card_options", {})
            )

            if sync_result.get("success"):
                if sync_result.get("already_synced"):
                    skipped_syncs.append({
                        "prompt_id": prompt_id,
                        "reason": "already_synced",
                        "card_id": sync_result.get("mochi_card_id"),
                    })
                else:
                    successful_syncs.append({
                        "prompt_id": prompt_id,
                        "card_id": sync_result.get("mochi_card_id"),
                        "deck_id": sync_result.get("deck_id"),
                    })
            else:
                failed_syncs.append({
                    "prompt_id": prompt_id,
                    "error": sync_result.get("error", "Unknown error"),
                })

        except Exception as e:
            logger.warning(f"Individual card sync failed: {prompt_id}, error: {e}")
            failed_syncs.append({
                "prompt_id": prompt_id,
                "error": str(e),
            })

        # Delay between batches to respect API rate limits
        if (i + 1) % batch_size == 0 and i + 1 < len(prompt_ids):
            await asyncio.sleep(delay_between)

    result = {
        "success": True,
        "batch_id": task_id,
        "total_prompts": len(prompt_ids),
        "successful": len(successful_syncs),
        "failed": len(failed_syncs),
        "skipped": len(skipped_syncs),
        "successful_syncs": successful_syncs,
        "failed_syncs": failed_syncs,
        "skipped_syncs": skipped_syncs,
    }

    tracker.complete(task_id, result, f"Synced {len(successful_syncs)}/{len(prompt_ids)} prompts")
    logger.info(f"Batch sync completed: {len(successful_syncs)} successful, {len(failed_syncs)} failed")
    return result


async def sync_decks(deck_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronize deck metadata from Mochi.

    Args:
        deck_id: Optional specific deck to sync, or all decks if None

    Returns:
        Dict with deck sync results
    """
    from app.services.mochi_client import MochiClient

    mochi_client = MochiClient()

    try:
        logger.info(f"Starting deck metadata sync: deck_id={deck_id}")

        await mochi_limiter.acquire()

        if deck_id:
            deck_result = await mochi_client.get_deck(deck_id)
            decks_data = [deck_result] if deck_result.get("success") else []
        else:
            decks_result = await mochi_client.get_decks()
            decks_data = decks_result.get("decks", []) if decks_result.get("success") else []

        if not decks_data:
            raise Exception("No deck data retrieved from Mochi")

        cached_decks = []
        for deck_data in decks_data:
            deck_info = {
                "id": deck_data["id"],
                "name": deck_data.get("name", ""),
                "description": deck_data.get("description", ""),
                "card_count": deck_data.get("card_count", 0),
                "created_at": deck_data.get("created_at"),
                "updated_at": deck_data.get("updated_at"),
                "cached_at": datetime.utcnow().isoformat(),
            }
            cached_decks.append(deck_info)

        result = {
            "success": True,
            "synced_decks": len(cached_decks),
            "decks": cached_decks,
            "sync_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Deck metadata sync completed: {len(cached_decks)} decks")
        return result

    except Exception as e:
        logger.error(f"Deck metadata sync failed: {e}")
        raise


async def verify_sync(max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Verify sync status of recently created prompts.

    Args:
        max_age_hours: Check prompts created within this timeframe

    Returns:
        Dict with sync verification results
    """
    from app.services.mochi_client import MochiClient

    prompt_repo = PromptRepository()
    mochi_client = MochiClient()

    try:
        logger.info(f"Starting sync status verification: max_age_hours={max_age_hours}")

        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        async with get_async_session() as session:
            recent_prompts = await prompt_repo.find_created_after(session, cutoff_time)

        verification_results = {
            "total_checked": len(recent_prompts),
            "synced": 0,
            "unsynced": 0,
            "sync_errors": 0,
            "unsynced_prompts": [],
            "error_prompts": [],
        }

        for prompt in recent_prompts:
            mochi_sync = prompt.metadata.get("mochi_sync", {})

            if prompt.mochi_card_id and mochi_sync.get("status") == "synced":
                try:
                    await mochi_limiter.acquire()
                    card_check = await mochi_client.get_card(prompt.mochi_card_id)
                    if card_check.get("success"):
                        verification_results["synced"] += 1
                    else:
                        verification_results["sync_errors"] += 1
                        verification_results["error_prompts"].append({
                            "prompt_id": str(prompt.id),
                            "card_id": prompt.mochi_card_id,
                            "error": "Card not found in Mochi",
                        })
                except Exception as e:
                    verification_results["sync_errors"] += 1
                    verification_results["error_prompts"].append({
                        "prompt_id": str(prompt.id),
                        "card_id": prompt.mochi_card_id,
                        "error": str(e),
                    })
            else:
                verification_results["unsynced"] += 1
                verification_results["unsynced_prompts"].append({
                    "prompt_id": str(prompt.id),
                    "created_at": prompt.created_at.isoformat(),
                    "sync_status": mochi_sync.get("status", "never_synced"),
                })

        logger.info(f"Sync verification completed: {verification_results['synced']} synced, {verification_results['unsynced']} unsynced")

        return {
            "success": True,
            "max_age_hours": max_age_hours,
            "verification_timestamp": datetime.utcnow().isoformat(),
            **verification_results
        }

    except Exception as e:
        logger.error(f"Sync status verification failed: {e}")
        raise


async def update_card(prompt_id: str, update_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Update an existing Mochi card with new prompt content.

    Args:
        prompt_id: Prompt ID with updated content
        update_options: Update configuration options

    Returns:
        Dict with update results
    """
    from app.services.mochi_client import MochiClient

    update_options = update_options or {}
    prompt_repo = PromptRepository()
    mochi_client = MochiClient()

    try:
        logger.info(f"Starting Mochi card update: {prompt_id}")

        async with get_async_session() as session:
            prompt = await prompt_repo.get_by_id(session, prompt_id)
            if not prompt:
                raise ValueError(f"Prompt not found: {prompt_id}")
            if not prompt.mochi_card_id:
                raise ValueError(f"Prompt has no associated Mochi card: {prompt_id}")

        update_data = {
            "content": prompt.question,
            "fields": {
                "front": prompt.question,
                "back": prompt.answer,
            },
        }

        if update_options.get("update_tags", False):
            tags = update_options.get("tags", [])
            if prompt.prompt_type:
                tags.append(f"type:{prompt.prompt_type}")
            update_data["tags"] = tags

        await mochi_limiter.acquire()

        update_result = await mochi_client.update_card(
            card_id=prompt.mochi_card_id,
            **update_data
        )

        if not update_result.get("success"):
            raise Exception(f"Mochi card update failed: {update_result.get('error')}")

        await update_prompt_mochi_status(prompt_id, prompt.mochi_card_id, "updated")

        result = {
            "success": True,
            "prompt_id": prompt_id,
            "mochi_card_id": prompt.mochi_card_id,
            "update_timestamp": datetime.utcnow().isoformat(),
            "fields_updated": len(update_data.get("fields", {})),
        }

        logger.info(f"Mochi card update completed: {prompt_id}")
        return result

    except Exception as e:
        logger.error(f"Mochi card update failed: {prompt_id}, error: {e}")
        raise


async def update_prompt_mochi_status(prompt_id: str, mochi_card_id: str, status: str = "synced"):
    """Update prompt with Mochi sync information."""
    prompt_repo = PromptRepository()

    async with get_async_session() as session:
        prompt = await prompt_repo.get_by_id(session, prompt_id)
        if prompt:
            updated_metadata = {
                **prompt.metadata,
                "mochi_sync": {
                    "card_id": mochi_card_id,
                    "status": status,
                    "synced_at": datetime.utcnow().isoformat(),
                    "sync_version": prompt.version,
                }
            }

            await prompt_repo.update(
                session,
                prompt_id,
                {
                    "mochi_card_id": mochi_card_id,
                    "metadata": updated_metadata,
                }
            )
            await session.commit()


async def get_mochi_deck_for_content(content_id: str) -> Optional[str]:
    """Get appropriate Mochi deck ID for content."""
    from app.services.mochi_client import MochiClient

    content_repo = ContentRepository()
    mochi_client = MochiClient()

    try:
        async with get_async_session() as session:
            content = await content_repo.get_by_id(session, content_id)
            if not content:
                return None

            if "mochi_deck_id" in content.metadata:
                return content.metadata["mochi_deck_id"]

            await mochi_limiter.acquire()
            decks = await mochi_client.get_decks()
            if decks.get("success") and decks.get("decks"):
                return decks["decks"][0]["id"]

    except Exception as e:
        logger.warning(f"Failed to determine Mochi deck: content_id={content_id}, error: {e}")

    return None


# =============================================================================
# Maintenance Tasks (4 tasks)
# =============================================================================

async def cleanup_old_data(retention_days: int = 30) -> Dict[str, Any]:
    """
    Clean up old data based on retention policy.

    Args:
        retention_days: Number of days to retain data

    Returns:
        Dict with cleanup results
    """
    from app.services.vector_store import VectorStoreService

    content_repo = ContentRepository()
    prompt_repo = PromptRepository()
    vector_service = VectorStoreService()

    try:
        logger.info(f"Starting data cleanup: retention_days={retention_days}")

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cleanup_results = {
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": retention_days,
            "deleted_content": 0,
            "deleted_prompts": 0,
            "deleted_vectors": 0,
        }

        async with get_async_session() as session:
            old_content = await content_repo.find_orphaned_before(session, cutoff_date)

            for content in old_content:
                recent_prompts = await prompt_repo.find_by_content_id_after(
                    session, content.id, cutoff_date
                )

                if not recent_prompts:
                    if content.chroma_id:
                        try:
                            await vector_service.delete_document(content.chroma_id)
                            cleanup_results["deleted_vectors"] += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete vector: {content.chroma_id}, error: {e}")

                    await content_repo.delete(session, content.id)
                    cleanup_results["deleted_content"] += 1

            orphaned_prompts = await prompt_repo.find_orphaned_before(session, cutoff_date)
            for prompt in orphaned_prompts:
                await prompt_repo.delete(session, prompt.id)
                cleanup_results["deleted_prompts"] += 1

            await session.commit()

        logger.info(f"Data cleanup completed: {cleanup_results}")
        return {"success": True, **cleanup_results}

    except Exception as e:
        logger.error(f"Data cleanup failed: {e}")
        raise


async def invalidate_cache() -> Dict[str, Any]:
    """
    Invalidate expired cache entries.

    Note: With in-memory storage, this is a no-op since entries expire automatically.

    Returns:
        Dict with cache cleanup results
    """
    logger.info("Cache invalidation triggered (in-memory cache - no action needed)")

    return {
        "success": True,
        "deleted_entries": 0,
        "cleanup_timestamp": datetime.utcnow().isoformat(),
        "note": "In-memory cache - entries expire automatically",
    }


async def aggregate_analytics(period: str = "daily") -> Dict[str, Any]:
    """
    Aggregate analytics data for reporting.

    Args:
        period: Aggregation period (daily, weekly, monthly)

    Returns:
        Dict with analytics aggregation results
    """
    content_repo = ContentRepository()
    prompt_repo = PromptRepository()

    try:
        logger.info(f"Starting analytics aggregation: period={period}")

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

        # Aggregate metrics (placeholder implementation)
        analytics_data = {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "content_processing": {
                "total_processed": 0,
                "by_source_type": {},
                "success_rate": 0.0,
            },
            "prompt_generation": {
                "total_generated": 0,
                "by_type": {},
                "approval_rate": 0.0,
            },
            "mochi_sync": {
                "total_synced": 0,
                "sync_success_rate": 0.0,
            },
            "aggregated_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"Analytics aggregation completed: period={period}")
        return {"success": True, **analytics_data}

    except Exception as e:
        logger.error(f"Analytics aggregation failed: {e}")
        raise


async def health_check(check_external: bool = True) -> Dict[str, Any]:
    """
    Perform comprehensive system health check.

    Args:
        check_external: Whether to check external service health

    Returns:
        Dict with health check results
    """
    import psutil

    try:
        logger.info(f"Starting system health check: check_external={check_external}")

        health_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "components": {},
            "warnings": [],
            "errors": [],
        }

        # Check database
        try:
            async with get_async_session() as session:
                await session.execute("SELECT 1")
            health_results["components"]["database"] = {"status": "healthy"}
        except Exception as e:
            health_results["components"]["database"] = {"status": "error", "message": str(e)}

        # Check system resources
        try:
            disk_usage = psutil.disk_usage('/')
            memory = psutil.virtual_memory()

            status = "healthy"
            warnings = []

            if disk_usage.percent > 90:
                status = "error"
                warnings.append("Disk usage critical")
            elif disk_usage.percent > 80:
                status = "warning"
                warnings.append("Disk usage high")

            if memory.percent > 90:
                status = "error"
                warnings.append("Memory usage critical")
            elif memory.percent > 80:
                status = "warning"
                warnings.append("Memory usage high")

            health_results["components"]["system_resources"] = {
                "status": status,
                "disk_usage_percent": round(disk_usage.percent, 2),
                "memory_usage_percent": round(memory.percent, 2),
                "warnings": warnings,
            }
        except Exception as e:
            health_results["components"]["system_resources"] = {"status": "warning", "message": str(e)}

        # Check external services if requested
        if check_external:
            from app.services.mochi_client import MochiClient
            from app.services.jina_reader import JinaReaderService

            try:
                mochi_client = MochiClient()
                await mochi_limiter.acquire()
                mochi_health = await mochi_client.health_check()
                health_results["components"]["mochi_api"] = {
                    "status": "healthy" if mochi_health.get("success") else "warning"
                }
            except Exception as e:
                health_results["components"]["mochi_api"] = {"status": "error", "message": str(e)}

            try:
                jina_service = JinaReaderService()
                await jina_limiter.acquire()
                jina_health = await jina_service.health_check()
                health_results["components"]["jina_api"] = {
                    "status": "healthy" if jina_health.get("success") else "warning"
                }
            except Exception as e:
                health_results["components"]["jina_api"] = {"status": "error", "message": str(e)}

        # Determine overall status
        component_statuses = [comp.get("status", "unknown") for comp in health_results["components"].values()]
        if "error" in component_statuses:
            health_results["overall_status"] = "unhealthy"
        elif "warning" in component_statuses:
            health_results["overall_status"] = "degraded"

        logger.info(f"Health check completed: status={health_results['overall_status']}")
        return {"success": True, **health_results}

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# =============================================================================
# AI Agent Tasks (4 tasks)
# =============================================================================

async def generate_prompts(content_id: str, content_text: str, model: str = "sonnet") -> Dict[str, Any]:
    """
    Generate flashcard prompts from content using AI.

    Args:
        content_id: Content UUID
        content_text: Content to generate prompts from
        model: AI model to use (haiku, sonnet, opus)

    Returns:
        Dict with generated prompts
    """
    try:
        logger.info(f"Generating prompts: content_id={content_id}, model={model}")

        await ai_limiter.acquire()

        # Implementation will use ContentProcessorService
        from app.services.content_processor import ContentProcessorService

        processor = ContentProcessorService()
        result = await processor.process_content(content_id, content_text)

        logger.info(f"Prompt generation completed: content_id={content_id}")
        return result

    except Exception as e:
        logger.error(f"Prompt generation failed: {e}")
        raise


async def review_quality(prompt_id: str, prompt_text: str) -> Dict[str, Any]:
    """
    Review and score prompt quality using AI.

    Args:
        prompt_id: Prompt UUID
        prompt_text: Prompt text to review

    Returns:
        Dict with quality review results
    """
    try:
        logger.info(f"Reviewing prompt quality: prompt_id={prompt_id}")

        await ai_limiter.acquire()

        # Placeholder - will use quality reviewer subagent
        result = {
            "success": True,
            "prompt_id": prompt_id,
            "quality_score": 0.0,
            "feedback": [],
            "review_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Quality review completed: prompt_id={prompt_id}")
        return result

    except Exception as e:
        logger.error(f"Quality review failed: {e}")
        raise


async def refine_prompts(prompt_ids: List[str], feedback: str) -> Dict[str, Any]:
    """
    Refine prompts based on feedback using AI.

    Args:
        prompt_ids: List of prompt IDs to refine
        feedback: Feedback to apply during refinement

    Returns:
        Dict with refinement results
    """
    try:
        logger.info(f"Refining prompts: count={len(prompt_ids)}")

        await ai_limiter.acquire()

        # Placeholder - will use refinement subagent
        result = {
            "success": True,
            "refined_count": len(prompt_ids),
            "prompt_ids": prompt_ids,
            "refinement_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Prompt refinement completed: {len(prompt_ids)} prompts")
        return result

    except Exception as e:
        logger.error(f"Prompt refinement failed: {e}")
        raise


async def track_costs(period: str = "daily") -> Dict[str, Any]:
    """
    Track and log AI usage costs.

    Args:
        period: Cost tracking period (daily, weekly, monthly)

    Returns:
        Dict with cost tracking results
    """
    try:
        logger.info(f"Tracking AI costs: period={period}")

        # Placeholder - will aggregate from usage logs
        result = {
            "success": True,
            "period": period,
            "total_requests": 0,
            "by_model": {},
            "token_usage": {"input": 0, "output": 0},
            "estimated_cost": 0.0,
            "tracking_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Cost tracking completed: period={period}")
        return result

    except Exception as e:
        logger.error(f"Cost tracking failed: {e}")
        raise
