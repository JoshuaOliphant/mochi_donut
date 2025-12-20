# ABOUTME: Vector store service for semantic search and embeddings
# ABOUTME: Wrapper around chroma_client for vector database operations

import logging
from typing import Optional, Dict, List, Any
from app.integrations.chroma_client import chroma_client

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing vector embeddings and semantic search."""

    def __init__(self):
        """Initialize the vector store service."""
        self.client = chroma_client

    async def add_document(
        self,
        collection_name: str,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add a document to the vector store.

        Args:
            collection_name: Name of the collection
            document_id: Unique document identifier
            content: Content to embed
            metadata: Optional metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.client.add_document(
                collection_name=collection_name,
                document_id=document_id,
                content=content,
                metadata=metadata or {}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add document to vector store: {e}")
            return False

    async def search(
        self,
        collection_name: str,
        query: str,
        n_results: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            collection_name: Name of the collection
            query: Search query
            n_results: Number of results to return
            threshold: Similarity threshold

        Returns:
            List of search results
        """
        try:
            results = await self.client.search_similar(
                collection_name=collection_name,
                query_text=query,
                n_results=n_results,
                similarity_threshold=threshold
            )
            return [
                {
                    "document_id": r.document_id,
                    "content": r.content,
                    "similarity_score": r.similarity_score,
                    "metadata": r.metadata
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Failed to search vector store: {e}")
            return []

    async def delete_document(
        self,
        collection_name: str,
        document_id: str
    ) -> bool:
        """
        Delete a document from the vector store.

        Args:
            collection_name: Name of the collection
            document_id: Document identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.client.delete_document(
                collection_name=collection_name,
                document_id=document_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete document from vector store: {e}")
            return False
