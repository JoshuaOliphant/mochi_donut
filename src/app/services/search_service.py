"""
Search service for semantic content search using Chroma vector database.

Provides content discovery, similarity search, and duplicate detection
capabilities powered by vector embeddings.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.integrations.chroma_client import ChromaClient, SearchResult, DuplicateCheckResult
from app.repositories.content import ContentRepository
from app.schemas.content import ContentSearchRequest, ContentSearchResponse
from app.core.config import settings

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service for semantic content search and discovery.

    Features:
    - Semantic similarity search across content
    - Duplicate content detection
    - Content clustering and recommendations
    - Search result ranking and filtering
    """

    CONTENT_COLLECTION = "content_embeddings"
    CONCEPTS_COLLECTION = "concept_embeddings"

    def __init__(
        self,
        chroma_client: ChromaClient,
        content_repo: ContentRepository
    ):
        self.chroma_client = chroma_client
        self.content_repo = content_repo

    async def search_content(
        self,
        search_request: ContentSearchRequest
    ) -> ContentSearchResponse:
        """
        Search for similar content using semantic similarity.

        Args:
            search_request: Search parameters and query

        Returns:
            ContentSearchResponse with matching content
        """
        try:
            # Perform semantic search in Chroma
            search_results = await self.chroma_client.search_similar(
                collection_name=self.CONTENT_COLLECTION,
                query_text=search_request.query,
                n_results=search_request.limit or 10,
                similarity_threshold=search_request.similarity_threshold or 0.7
            )

            # Enrich results with database content
            enriched_results = []
            for result in search_results:
                try:
                    # Get full content from database
                    content = await self.content_repo.get_by_chroma_id(result.document_id)
                    if content:
                        enriched_results.append({
                            "content_id": str(content.id),
                            "title": content.title,
                            "source_url": content.source_url,
                            "similarity_score": result.similarity_score,
                            "snippet": result.content[:200] + "..." if len(result.content) > 200 else result.content,
                            "word_count": content.word_count,
                            "created_at": content.created_at.isoformat(),
                            "processing_status": content.processing_status,
                            "metadata": result.metadata
                        })
                except Exception as e:
                    logger.warning(f"Failed to enrich search result {result.document_id}: {str(e)}")
                    continue

            return ContentSearchResponse(
                query=search_request.query,
                results=enriched_results,
                total_results=len(enriched_results),
                similarity_threshold=search_request.similarity_threshold or 0.7,
                search_metadata={
                    "searched_at": datetime.utcnow().isoformat(),
                    "collection": self.CONTENT_COLLECTION,
                    "processing_time_ms": 0  # TODO: Add timing
                }
            )

        except Exception as e:
            logger.error(f"Content search failed: {str(e)}")
            raise ValueError(f"Search operation failed: {str(e)}")

    async def check_content_duplicates(
        self,
        content: str,
        similarity_threshold: float = 0.85
    ) -> DuplicateCheckResult:
        """
        Check if content is similar to existing content (duplicate detection).

        Args:
            content: Content to check for duplicates
            similarity_threshold: Minimum similarity to consider as duplicate

        Returns:
            DuplicateCheckResult with duplicate status and similar content
        """
        try:
            return await self.chroma_client.check_for_duplicates(
                collection_name=self.CONTENT_COLLECTION,
                content=content,
                similarity_threshold=similarity_threshold,
                max_results=5
            )

        except Exception as e:
            logger.error(f"Duplicate check failed: {str(e)}")
            raise ValueError(f"Duplicate check failed: {str(e)}")

    async def find_related_content(
        self,
        content_id: str,
        max_results: int = 5,
        similarity_threshold: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Find content related to a specific piece of content.

        Args:
            content_id: ID of the content to find relations for
            max_results: Maximum number of related items to return
            similarity_threshold: Minimum similarity threshold

        Returns:
            List of related content items
        """
        try:
            # Get the original content
            content = await self.content_repo.get(content_id)
            if not content:
                raise ValueError(f"Content {content_id} not found")

            # Search for similar content using the content text
            search_results = await self.chroma_client.search_similar(
                collection_name=self.CONTENT_COLLECTION,
                query_text=content.markdown_content[:1000],  # Use first 1000 chars
                n_results=max_results + 1,  # +1 to exclude self
                similarity_threshold=similarity_threshold
            )

            # Filter out the original content and enrich results
            related_content = []
            for result in search_results:
                if result.document_id != str(content_id):
                    try:
                        related = await self.content_repo.get_by_chroma_id(result.document_id)
                        if related:
                            related_content.append({
                                "content_id": str(related.id),
                                "title": related.title,
                                "source_url": related.source_url,
                                "similarity_score": result.similarity_score,
                                "created_at": related.created_at.isoformat(),
                                "word_count": related.word_count
                            })
                    except Exception as e:
                        logger.warning(f"Failed to get related content {result.document_id}: {str(e)}")
                        continue

            return related_content[:max_results]

        except Exception as e:
            logger.error(f"Related content search failed: {str(e)}")
            raise ValueError(f"Related content search failed: {str(e)}")

    async def search_concepts(
        self,
        query: str,
        max_results: int = 20,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for concepts across all content.

        Args:
            query: Concept search query
            max_results: Maximum number of results
            similarity_threshold: Minimum similarity threshold

        Returns:
            List of matching concepts with source content
        """
        try:
            search_results = await self.chroma_client.search_similar(
                collection_name=self.CONCEPTS_COLLECTION,
                query_text=query,
                n_results=max_results,
                similarity_threshold=similarity_threshold
            )

            concepts = []
            for result in search_results:
                concepts.append({
                    "concept": result.content,
                    "similarity_score": result.similarity_score,
                    "source_content_id": result.metadata.get("content_id"),
                    "extraction_metadata": result.metadata
                })

            return concepts

        except Exception as e:
            logger.error(f"Concept search failed: {str(e)}")
            raise ValueError(f"Concept search failed: {str(e)}")

    async def get_search_suggestions(
        self,
        partial_query: str,
        max_suggestions: int = 5
    ) -> List[str]:
        """
        Get search suggestions based on partial query.

        Args:
            partial_query: Partial search query
            max_suggestions: Maximum number of suggestions

        Returns:
            List of suggested search terms
        """
        try:
            # Simple implementation using existing content titles and concepts
            # In a more advanced implementation, this could use a dedicated suggestions index

            search_results = await self.chroma_client.search_similar(
                collection_name=self.CONTENT_COLLECTION,
                query_text=partial_query,
                n_results=max_suggestions * 2,
                similarity_threshold=0.3  # Lower threshold for suggestions
            )

            suggestions = []
            for result in search_results:
                # Extract potential search terms from metadata
                if "title" in result.metadata:
                    title_words = result.metadata["title"].split()
                    for word in title_words:
                        if len(word) > 3 and word.lower().startswith(partial_query.lower()):
                            if word not in suggestions:
                                suggestions.append(word)

            return suggestions[:max_suggestions]

        except Exception as e:
            logger.error(f"Search suggestions failed: {str(e)}")
            return []  # Return empty list on error, don't raise

    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the search collections.

        Returns:
            Dictionary with collection statistics
        """
        try:
            content_stats = await self.chroma_client.get_collection_stats(self.CONTENT_COLLECTION)

            try:
                concept_stats = await self.chroma_client.get_collection_stats(self.CONCEPTS_COLLECTION)
            except Exception:
                # Concepts collection might not exist yet
                concept_stats = {
                    "collection_name": self.CONCEPTS_COLLECTION,
                    "document_count": 0,
                    "collection_metadata": {},
                    "last_updated": datetime.utcnow().isoformat()
                }

            return {
                "content_collection": content_stats,
                "concepts_collection": concept_stats,
                "total_documents": content_stats["document_count"] + concept_stats["document_count"],
                "last_updated": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            raise ValueError(f"Failed to get collection stats: {str(e)}")

    async def reindex_content(self, content_id: str) -> bool:
        """
        Reindex specific content in the vector database.

        Args:
            content_id: ID of content to reindex

        Returns:
            True if reindexing succeeded
        """
        try:
            content = await self.content_repo.get(content_id)
            if not content:
                raise ValueError(f"Content {content_id} not found")

            # Remove existing document
            try:
                await self.chroma_client.delete_document(
                    collection_name=self.CONTENT_COLLECTION,
                    document_id=str(content_id)
                )
            except Exception:
                pass  # Document might not exist

            # Re-add document
            await self.chroma_client.add_document(
                collection_name=self.CONTENT_COLLECTION,
                document_id=str(content_id),
                content=content.markdown_content,
                metadata={
                    "title": content.title,
                    "source_url": content.source_url,
                    "content_id": str(content_id),
                    "word_count": content.word_count,
                    "created_at": content.created_at.isoformat(),
                    "reindexed_at": datetime.utcnow().isoformat()
                }
            )

            logger.info(f"Successfully reindexed content {content_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to reindex content {content_id}: {str(e)}")
            return False