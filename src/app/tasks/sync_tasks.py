"""
Mochi synchronization tasks for the Mochi Donut system.

Handles background synchronization with Mochi API including
card creation, batch operations, and sync verification.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import structlog

from app.tasks.celery_app import celery_app, TaskConfig
from app.services.mochi_client import MochiClient
from app.services.cache import CacheService
from app.repositories.prompt import PromptRepository
from app.repositories.content import ContentRepository
from app.db.session import get_async_session
from app.schemas.prompt import PromptUpdate

logger = structlog.get_logger()


class MochiSyncTask:
    """Base class for Mochi sync tasks with common utilities."""

    def __init__(self):
        self.mochi_client = MochiClient()
        self.cache_service = CacheService()
        self.prompt_repo = PromptRepository()
        self.content_repo = ContentRepository()

    async def update_prompt_mochi_status(self, prompt_id: str, mochi_card_id: str, status: str = "synced"):
        """Update prompt with Mochi sync information."""
        async with get_async_session() as session:
            prompt = await self.prompt_repo.get_by_id(session, prompt_id)
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

                await self.prompt_repo.update(
                    session,
                    prompt_id,
                    {
                        "mochi_card_id": mochi_card_id,
                        "metadata": updated_metadata,
                    }
                )
                await session.commit()

    async def get_mochi_deck_for_content(self, content_id: str) -> Optional[str]:
        """Get appropriate Mochi deck ID for content."""
        try:
            async with get_async_session() as session:
                content = await self.content_repo.get_by_id(session, content_id)
                if not content:
                    return None

                # Check for explicit deck mapping
                if "mochi_deck_id" in content.metadata:
                    return content.metadata["mochi_deck_id"]

                # Use source type or URL to determine deck
                source_domain = content.source_url.split('/')[2] if content.source_url else "unknown"

                # Cache deck mappings
                cache_key = f"mochi:deck_mapping:{source_domain}"
                cached_deck = await self.cache_service.get(cache_key)

                if cached_deck:
                    return cached_deck

                # Get available decks and find best match
                decks = await self.mochi_client.get_decks()
                if decks.get("success") and decks.get("decks"):
                    # Simple mapping logic - could be made more sophisticated
                    default_deck = decks["decks"][0]["id"]  # Use first available deck

                    # Cache the mapping
                    await self.cache_service.set(cache_key, default_deck, ttl=86400)  # 24 hours
                    return default_deck

        except Exception as e:
            logger.warning("Failed to determine Mochi deck", content_id=content_id, error=str(e))

        return None


@celery_app.task(bind=True, base=MochiSyncTask, **TaskConfig.get_retry_config("external_api"))
def create_mochi_card(self, prompt_id: str, deck_id: Optional[str] = None, card_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Create a single Mochi card from a prompt.

    Args:
        prompt_id: Prompt UUID to convert to card
        deck_id: Optional specific deck ID
        card_options: Additional card creation options

    Returns:
        Dict with card creation results
    """
    task_logger = TaskConfig.get_task_logger("create_mochi_card")
    card_options = card_options or {}

    try:
        task_logger.info("Starting Mochi card creation", prompt_id=prompt_id, task_id=self.request.id)

        # Get prompt from database
        async def get_prompt():
            async with get_async_session() as session:
                prompt = await self.prompt_repo.get_by_id(session, prompt_id)
                if not prompt:
                    raise ValueError(f"Prompt not found: {prompt_id}")
                return prompt

        prompt = asyncio.run(get_prompt())

        # Check if already synced (unless force_resync)
        if (prompt.mochi_card_id and
            not card_options.get("force_resync", False) and
            prompt.metadata.get("mochi_sync", {}).get("status") == "synced"):

            return {
                "success": True,
                "already_synced": True,
                "prompt_id": prompt_id,
                "mochi_card_id": prompt.mochi_card_id,
            }

        # Determine deck ID
        if not deck_id:
            deck_id = asyncio.run(self.get_mochi_deck_for_content(prompt.content_id))

        if not deck_id:
            raise ValueError("No suitable Mochi deck found")

        # Prepare card data
        card_data = {
            "content": prompt.question,
            "deck-id": deck_id,
            "template-id": card_options.get("template_id"),  # Optional
            "fields": {
                "front": prompt.question,
                "back": prompt.answer,
            },
            "tags": card_options.get("tags", []),
        }

        # Add metadata as tags if requested
        if card_options.get("include_metadata_tags", True):
            metadata_tags = []

            # Add prompt type tag
            if prompt.prompt_type:
                metadata_tags.append(f"type:{prompt.prompt_type}")

            # Add confidence level tag
            if prompt.confidence_score:
                confidence_level = "high" if prompt.confidence_score > 0.8 else "medium" if prompt.confidence_score > 0.5 else "low"
                metadata_tags.append(f"confidence:{confidence_level}")

            # Add source domain tag
            content = asyncio.run(get_prompt().content if hasattr(get_prompt(), 'content') else None)
            if content and content.source_url:
                domain = content.source_url.split('/')[2]
                metadata_tags.append(f"source:{domain}")

            card_data["tags"].extend(metadata_tags)

        # Create card via Mochi API
        task_logger.info("Creating card in Mochi", prompt_id=prompt_id, deck_id=deck_id)

        creation_result = asyncio.run(self.mochi_client.create_card(
            content=card_data["content"],
            deck_id=deck_id,
            template_id=card_data.get("template-id"),
            fields=card_data["fields"],
            tags=card_data.get("tags", [])
        ))

        if not creation_result.get("success"):
            raise Exception(f"Mochi card creation failed: {creation_result.get('error')}")

        mochi_card_id = creation_result.get("card_id")

        # Update prompt with Mochi card information
        asyncio.run(self.update_prompt_mochi_status(prompt_id, mochi_card_id, "synced"))

        result = {
            "success": True,
            "prompt_id": prompt_id,
            "mochi_card_id": mochi_card_id,
            "deck_id": deck_id,
            "tags_added": len(card_data.get("tags", [])),
            "sync_timestamp": datetime.utcnow().isoformat(),
        }

        task_logger.info(
            "Mochi card creation completed",
            prompt_id=prompt_id,
            card_id=mochi_card_id
        )

        return result

    except Exception as e:
        task_logger.error("Mochi card creation failed", prompt_id=prompt_id, error=str(e))
        raise self.retry(countdown=30, max_retries=5, exc=e)


@celery_app.task(bind=True, base=MochiSyncTask, **TaskConfig.get_retry_config("external_api"))
def batch_sync_cards(self, prompt_ids: List[str], batch_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Synchronize multiple prompts to Mochi cards in batch.

    Args:
        prompt_ids: List of prompt IDs to sync
        batch_options: Batch sync configuration

    Returns:
        Dict with batch sync results
    """
    task_logger = TaskConfig.get_task_logger("batch_sync_cards")
    batch_options = batch_options or {}

    try:
        task_logger.info("Starting batch Mochi sync", prompt_count=len(prompt_ids), task_id=self.request.id)

        # Initialize progress tracking
        batch_id = self.request.id
        cache_key = f"mochi_sync:progress:{batch_id}"

        async def update_progress(processed: int, total: int, current_prompt: str = ""):
            progress_data = {
                "batch_id": batch_id,
                "processed": processed,
                "total": total,
                "progress_percent": (processed / total) * 100 if total > 0 else 0,
                "current_prompt": current_prompt,
                "status": "processing" if processed < total else "completed",
            }
            await self.cache_service.set(cache_key, json.dumps(progress_data), ttl=3600)

        # Process prompts in smaller batches to respect API limits
        batch_size = batch_options.get("batch_size", 5)
        delay_between_batches = batch_options.get("delay_seconds", 2)

        successful_syncs = []
        failed_syncs = []
        skipped_syncs = []

        asyncio.run(update_progress(0, len(prompt_ids)))

        for i in range(0, len(prompt_ids), batch_size):
            batch_prompt_ids = prompt_ids[i:i + batch_size]

            # Process each prompt in the current batch
            for prompt_id in batch_prompt_ids:
                try:
                    asyncio.run(update_progress(
                        len(successful_syncs) + len(failed_syncs) + len(skipped_syncs),
                        len(prompt_ids),
                        prompt_id
                    ))

                    # Create individual card
                    sync_result = create_mochi_card.delay(
                        prompt_id=prompt_id,
                        deck_id=batch_options.get("deck_id"),
                        card_options=batch_options.get("card_options", {})
                    ).get(timeout=120)  # 2 minute timeout per card

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
                    task_logger.warning("Individual card sync failed", prompt_id=prompt_id, error=str(e))
                    failed_syncs.append({
                        "prompt_id": prompt_id,
                        "error": str(e),
                    })

            # Delay between batches to respect API rate limits
            if i + batch_size < len(prompt_ids):
                await asyncio.sleep(delay_between_batches)

        # Final progress update
        asyncio.run(update_progress(len(prompt_ids), len(prompt_ids)))

        # Summary result
        result = {
            "success": True,
            "batch_id": batch_id,
            "total_prompts": len(prompt_ids),
            "successful": len(successful_syncs),
            "failed": len(failed_syncs),
            "skipped": len(skipped_syncs),
            "successful_syncs": successful_syncs,
            "failed_syncs": failed_syncs,
            "skipped_syncs": skipped_syncs,
            "processing_time": datetime.utcnow().isoformat(),
        }

        task_logger.info(
            "Batch Mochi sync completed",
            batch_id=batch_id,
            successful=len(successful_syncs),
            failed=len(failed_syncs),
            skipped=len(skipped_syncs)
        )

        return result

    except Exception as e:
        task_logger.error("Batch Mochi sync failed", error=str(e))
        raise self.retry(countdown=60, max_retries=3, exc=e)


@celery_app.task(bind=True, base=MochiSyncTask, **TaskConfig.get_retry_config("external_api"))
def sync_deck_metadata(self, deck_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronize deck metadata from Mochi.

    Args:
        deck_id: Optional specific deck to sync, or all decks if None

    Returns:
        Dict with deck sync results
    """
    task_logger = TaskConfig.get_task_logger("sync_deck_metadata")

    try:
        task_logger.info("Starting deck metadata sync", deck_id=deck_id, task_id=self.request.id)

        # Get deck information from Mochi
        if deck_id:
            deck_result = asyncio.run(self.mochi_client.get_deck(deck_id))
            decks_data = [deck_result] if deck_result.get("success") else []
        else:
            decks_result = asyncio.run(self.mochi_client.get_decks())
            decks_data = decks_result.get("decks", []) if decks_result.get("success") else []

        if not decks_data:
            raise Exception("No deck data retrieved from Mochi")

        # Cache deck information
        cached_decks = []
        for deck_data in decks_data:
            deck_cache_key = f"mochi:deck:{deck_data['id']}"
            deck_info = {
                "id": deck_data["id"],
                "name": deck_data.get("name", ""),
                "description": deck_data.get("description", ""),
                "card_count": deck_data.get("card_count", 0),
                "created_at": deck_data.get("created_at"),
                "updated_at": deck_data.get("updated_at"),
                "cached_at": datetime.utcnow().isoformat(),
            }

            await self.cache_service.set(deck_cache_key, json.dumps(deck_info), ttl=86400)  # 24 hours
            cached_decks.append(deck_info)

        # Update global deck list cache
        all_decks_key = "mochi:decks:all"
        if not deck_id:  # Only update full list if we synced all decks
            await self.cache_service.set(all_decks_key, json.dumps(cached_decks), ttl=3600)  # 1 hour

        result = {
            "success": True,
            "synced_decks": len(cached_decks),
            "decks": cached_decks,
            "sync_timestamp": datetime.utcnow().isoformat(),
        }

        task_logger.info(
            "Deck metadata sync completed",
            synced_count=len(cached_decks)
        )

        return result

    except Exception as e:
        task_logger.error("Deck metadata sync failed", deck_id=deck_id, error=str(e))
        raise self.retry(countdown=60, max_retries=3, exc=e)


@celery_app.task(bind=True, base=MochiSyncTask, **TaskConfig.get_retry_config("maintenance"))
def verify_sync_status(self, max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Verify sync status of recently created prompts.

    Args:
        max_age_hours: Check prompts created within this timeframe

    Returns:
        Dict with sync verification results
    """
    task_logger = TaskConfig.get_task_logger("verify_sync_status")

    try:
        task_logger.info("Starting sync status verification", max_age_hours=max_age_hours, task_id=self.request.id)

        # Get recent prompts that should be synced
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        async def get_recent_prompts():
            async with get_async_session() as session:
                # This would query for prompts created after cutoff_time
                # Implementation depends on actual repository methods
                prompts = await self.prompt_repo.find_created_after(session, cutoff_time)
                return prompts

        recent_prompts = asyncio.run(get_recent_prompts())

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
                # Verify card still exists in Mochi
                try:
                    card_check = asyncio.run(self.mochi_client.get_card(prompt.mochi_card_id))
                    if card_check.get("success"):
                        verification_results["synced"] += 1
                    else:
                        verification_results["sync_errors"] += 1
                        verification_results["error_prompts"].append({
                            "prompt_id": prompt.id,
                            "card_id": prompt.mochi_card_id,
                            "error": "Card not found in Mochi",
                        })
                except Exception as e:
                    verification_results["sync_errors"] += 1
                    verification_results["error_prompts"].append({
                        "prompt_id": prompt.id,
                        "card_id": prompt.mochi_card_id,
                        "error": str(e),
                    })
            else:
                verification_results["unsynced"] += 1
                verification_results["unsynced_prompts"].append({
                    "prompt_id": prompt.id,
                    "created_at": prompt.created_at.isoformat(),
                    "sync_status": mochi_sync.get("status", "never_synced"),
                })

        # Trigger resync for unsynced prompts if requested
        if verification_results["unsynced_prompts"]:
            unsynced_ids = [p["prompt_id"] for p in verification_results["unsynced_prompts"]]
            resync_task = batch_sync_cards.delay(
                prompt_ids=unsynced_ids,
                batch_options={"batch_size": 3, "delay_seconds": 5}
            )
            verification_results["resync_task_id"] = resync_task.id

        task_logger.info(
            "Sync status verification completed",
            total_checked=verification_results["total_checked"],
            synced=verification_results["synced"],
            unsynced=verification_results["unsynced"],
            errors=verification_results["sync_errors"]
        )

        return {
            "success": True,
            "max_age_hours": max_age_hours,
            "verification_timestamp": datetime.utcnow().isoformat(),
            **verification_results
        }

    except Exception as e:
        task_logger.error("Sync status verification failed", error=str(e))
        raise self.retry(countdown=300, max_retries=1, exc=e)


@celery_app.task(bind=True, base=MochiSyncTask, **TaskConfig.get_retry_config("external_api"))
def update_mochi_card(self, prompt_id: str, update_options: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Update an existing Mochi card with new prompt content.

    Args:
        prompt_id: Prompt ID with updated content
        update_options: Update configuration options

    Returns:
        Dict with update results
    """
    task_logger = TaskConfig.get_task_logger("update_mochi_card")
    update_options = update_options or {}

    try:
        task_logger.info("Starting Mochi card update", prompt_id=prompt_id, task_id=self.request.id)

        # Get prompt with existing Mochi card ID
        async def get_prompt():
            async with get_async_session() as session:
                prompt = await self.prompt_repo.get_by_id(session, prompt_id)
                if not prompt:
                    raise ValueError(f"Prompt not found: {prompt_id}")
                if not prompt.mochi_card_id:
                    raise ValueError(f"Prompt has no associated Mochi card: {prompt_id}")
                return prompt

        prompt = asyncio.run(get_prompt())

        # Prepare updated card data
        update_data = {
            "content": prompt.question,
            "fields": {
                "front": prompt.question,
                "back": prompt.answer,
            },
        }

        # Add tags if requested
        if update_options.get("update_tags", False):
            tags = update_options.get("tags", [])
            if prompt.prompt_type:
                tags.append(f"type:{prompt.prompt_type}")
            update_data["tags"] = tags

        # Update card in Mochi
        update_result = asyncio.run(self.mochi_client.update_card(
            card_id=prompt.mochi_card_id,
            **update_data
        ))

        if not update_result.get("success"):
            raise Exception(f"Mochi card update failed: {update_result.get('error')}")

        # Update prompt metadata
        asyncio.run(self.update_prompt_mochi_status(prompt_id, prompt.mochi_card_id, "updated"))

        result = {
            "success": True,
            "prompt_id": prompt_id,
            "mochi_card_id": prompt.mochi_card_id,
            "update_timestamp": datetime.utcnow().isoformat(),
            "fields_updated": len(update_data.get("fields", {})),
        }

        task_logger.info(
            "Mochi card update completed",
            prompt_id=prompt_id,
            card_id=prompt.mochi_card_id
        )

        return result

    except Exception as e:
        task_logger.error("Mochi card update failed", prompt_id=prompt_id, error=str(e))
        raise self.retry(countdown=30, max_retries=3, exc=e)