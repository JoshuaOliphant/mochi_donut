"""
Dependency injection and setup for external service integrations.

Provides singleton instances and proper dependency injection
for JinaAI, Chroma, and Mochi clients throughout the application.
"""

import logging
from functools import lru_cache
from typing import Optional

from app.core.config import settings
from app.integrations.jina_client import JinaAIClient
from app.integrations.chroma_client import ChromaClient
from app.integrations.mochi_client import MochiClient

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_jina_client() -> JinaAIClient:
    """
    Get singleton JinaAI client instance.

    Returns:
        JinaAIClient instance
    """
    logger.info("Initializing JinaAI client")
    return JinaAIClient()


@lru_cache(maxsize=1)
def get_chroma_client() -> ChromaClient:
    """
    Get singleton Chroma client instance.

    Returns:
        ChromaClient instance
    """
    logger.info("Initializing Chroma client")
    return ChromaClient()


@lru_cache(maxsize=1)
def get_mochi_client() -> MochiClient:
    """
    Get singleton Mochi client instance.

    Returns:
        MochiClient instance
    """
    logger.info("Initializing Mochi client")
    return MochiClient()


async def health_check_integrations() -> dict:
    """
    Check health status of all external service integrations.

    Returns:
        Dictionary with health status of each service
    """
    health_status = {
        "jina": {"healthy": False, "configured": bool(settings.JINA_API_KEY)},
        "chroma": {"healthy": False, "configured": True},
        "mochi": {"healthy": False, "configured": bool(settings.MOCHI_API_KEY)}
    }

    # Check JinaAI health
    try:
        jina_client = get_jina_client()
        # Simple test to check if client is functional
        health_status["jina"]["healthy"] = True
        logger.info("JinaAI client health check passed")
    except Exception as e:
        logger.warning(f"JinaAI client health check failed: {str(e)}")

    # Check Chroma health
    try:
        chroma_client = get_chroma_client()
        health_status["chroma"]["healthy"] = await chroma_client.health_check()
        if health_status["chroma"]["healthy"]:
            logger.info("Chroma client health check passed")
        else:
            logger.warning("Chroma client health check failed")
    except Exception as e:
        logger.warning(f"Chroma client health check failed: {str(e)}")

    # Check Mochi health
    try:
        mochi_client = get_mochi_client()
        health_status["mochi"]["healthy"] = await mochi_client.health_check()
        if health_status["mochi"]["healthy"]:
            logger.info("Mochi client health check passed")
        else:
            logger.warning("Mochi client health check failed")
    except Exception as e:
        logger.warning(f"Mochi client health check failed: {str(e)}")

    return health_status


async def initialize_integrations() -> dict:
    """
    Initialize all external service integrations.

    Returns:
        Dictionary with initialization status
    """
    logger.info("Initializing external service integrations")

    initialization_status = {
        "jina": {"initialized": False, "error": None},
        "chroma": {"initialized": False, "error": None},
        "mochi": {"initialized": False, "error": None}
    }

    # Initialize JinaAI
    try:
        get_jina_client()
        initialization_status["jina"]["initialized"] = True
        logger.info("JinaAI client initialized successfully")
    except Exception as e:
        error_msg = f"Failed to initialize JinaAI client: {str(e)}"
        initialization_status["jina"]["error"] = error_msg
        logger.error(error_msg)

    # Initialize Chroma
    try:
        chroma_client = get_chroma_client()
        # Ensure the main collections exist
        await chroma_client.get_or_create_collection(
            "content_embeddings",
            metadata={"description": "Mochi Donut content embeddings"}
        )
        await chroma_client.get_or_create_collection(
            "concept_embeddings",
            metadata={"description": "Mochi Donut concept embeddings"}
        )
        initialization_status["chroma"]["initialized"] = True
        logger.info("Chroma client initialized successfully")
    except Exception as e:
        error_msg = f"Failed to initialize Chroma client: {str(e)}"
        initialization_status["chroma"]["error"] = error_msg
        logger.error(error_msg)

    # Initialize Mochi
    try:
        get_mochi_client()
        initialization_status["mochi"]["initialized"] = True
        logger.info("Mochi client initialized successfully")
    except Exception as e:
        error_msg = f"Failed to initialize Mochi client: {str(e)}"
        initialization_status["mochi"]["error"] = error_msg
        logger.error(error_msg)

    return initialization_status


async def cleanup_integrations():
    """
    Clean up all external service integrations.
    """
    logger.info("Cleaning up external service integrations")

    # Clean up JinaAI client
    try:
        jina_client = get_jina_client()
        await jina_client.close()
        logger.info("JinaAI client cleaned up")
    except Exception as e:
        logger.warning(f"Error cleaning up JinaAI client: {str(e)}")

    # Clean up Mochi client
    try:
        mochi_client = get_mochi_client()
        await mochi_client.close()
        logger.info("Mochi client cleaned up")
    except Exception as e:
        logger.warning(f"Error cleaning up Mochi client: {str(e)}")

    # Chroma client doesn't need explicit cleanup

    # Clear the LRU cache to force new instances on next access
    get_jina_client.cache_clear()
    get_chroma_client.cache_clear()
    get_mochi_client.cache_clear()


def get_integration_info() -> dict:
    """
    Get information about available integrations.

    Returns:
        Dictionary with integration information
    """
    return {
        "jina": {
            "name": "JinaAI Reader API",
            "description": "Web content and PDF extraction",
            "api_key_configured": bool(settings.JINA_API_KEY),
            "features": ["web_content_extraction", "pdf_processing", "content_caching"]
        },
        "chroma": {
            "name": "Chroma Vector Database",
            "description": "Semantic search and content embeddings",
            "api_key_configured": bool(settings.CHROMA_API_KEY),
            "features": ["semantic_search", "duplicate_detection", "content_embeddings"]
        },
        "mochi": {
            "name": "Mochi Cards API",
            "description": "Flashcard creation and management",
            "api_key_configured": bool(settings.MOCHI_API_KEY),
            "features": ["card_creation", "deck_management", "batch_operations"]
        }
    }