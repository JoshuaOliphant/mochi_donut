# Content Processor Service
"""
Service layer for content processing orchestration.
Manages the content ingestion, processing pipeline, and AI agent coordination.
"""

import uuid
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import BackgroundTasks
import httpx

from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository
from app.schemas.content import (
    ContentProcessingRequest,
    ContentProcessingResponse,
    ContentBatchProcessingRequest,
    ContentBatchProcessingResponse,
    ContentCreate
)
from app.db.models import SourceType, ProcessingStatus
from app.core.config import settings
from app.integrations.jina_client import JinaAIClient
from app.integrations.chroma_client import ChromaClient


class ContentProcessorService:
    """Service for content processing and AI orchestration."""

    def __init__(
        self,
        content_repo: ContentRepository,
        prompt_repo: PromptRepository,
        jina_client: Optional[JinaAIClient] = None,
        chroma_client: Optional[ChromaClient] = None
    ):
        self.content_repo = content_repo
        self.prompt_repo = prompt_repo
        self.jina_client = jina_client or JinaAIClient()
        self.chroma_client = chroma_client or ChromaClient()

    async def submit_for_processing(
        self,
        processing_request: ContentProcessingRequest,
        background_tasks: BackgroundTasks
    ) -> ContentProcessingResponse:
        """Submit content for background processing."""
        try:
            # Extract or fetch content
            if processing_request.raw_content:
                markdown_content = processing_request.raw_content
                title = "Direct Content"
            else:
                # Fetch content from URL
                markdown_content, title = await self._fetch_content_from_url(
                    processing_request.source_url
                )

            # Create content record
            content_hash = self._generate_content_hash(markdown_content)

            # Check for duplicates
            existing_content = await self.content_repo.get_by_hash(content_hash)
            if existing_content:
                return ContentProcessingResponse(
                    content_id=existing_content.id,
                    processing_status=existing_content.processing_status,
                    message="Content already exists and is being processed",
                    estimated_completion=existing_content.processed_at
                )

            # Create new content record
            content_data = ContentCreate(
                source_url=processing_request.source_url,
                source_type=processing_request.source_type,
                title=title,
                markdown_content=markdown_content,
                content_hash=content_hash,
                word_count=len(markdown_content.split()),
                estimated_reading_time=self._estimate_reading_time(markdown_content),
                processing_config=processing_request.processing_config,
                metadata={
                    "submitted_at": datetime.utcnow().isoformat(),
                    "priority": processing_request.priority
                }
            )

            content = await self.content_repo.create(content_data)

            # Submit for background processing
            background_tasks.add_task(
                self._process_content_background,
                content.id,
                processing_request.processing_config or {}
            )

            # Estimate completion time (placeholder)
            estimated_completion = datetime.utcnow()  # TODO: Implement actual estimation

            return ContentProcessingResponse(
                content_id=content.id,
                processing_status=ProcessingStatus.PENDING,
                message="Content submitted for processing",
                estimated_completion=estimated_completion
            )

        except Exception as e:
            raise ValueError(f"Failed to submit content for processing: {str(e)}")

    async def submit_batch_for_processing(
        self,
        batch_request: ContentBatchProcessingRequest,
        background_tasks: BackgroundTasks
    ) -> ContentBatchProcessingResponse:
        """Submit multiple content items for batch processing."""
        try:
            batch_id = str(uuid.uuid4())
            results = []
            accepted_items = 0
            rejected_items = 0

            for item in batch_request.items:
                try:
                    result = await self.submit_for_processing(item, background_tasks)
                    results.append(result)
                    accepted_items += 1
                except Exception as e:
                    results.append(ContentProcessingResponse(
                        content_id=uuid.uuid4(),  # Placeholder
                        processing_status=ProcessingStatus.FAILED,
                        message=f"Failed to submit: {str(e)}"
                    ))
                    rejected_items += 1

            return ContentBatchProcessingResponse(
                batch_id=batch_id,
                total_items=len(batch_request.items),
                accepted_items=accepted_items,
                rejected_items=rejected_items,
                results=results
            )

        except Exception as e:
            raise ValueError(f"Failed to submit batch for processing: {str(e)}")

    async def _fetch_content_from_url(self, url: str) -> tuple[str, str]:
        """Fetch content from URL using JinaAI Reader API."""
        if not url:
            raise ValueError("URL is required")

        try:
            # Use the JinaAI client for content extraction
            result = await self.jina_client.extract_from_url(url, use_cache=True)
            return result.content, result.title

        except Exception as e:
            raise ValueError(f"Failed to fetch content from URL: {str(e)}")

    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content for deduplication."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _estimate_reading_time(self, content: str) -> int:
        """Estimate reading time in minutes (assuming 200 WPM)."""
        word_count = len(content.split())
        return max(1, word_count // 200)

    async def _process_content_background(
        self,
        content_id: uuid.UUID,
        processing_config: Dict[str, Any]
    ):
        """Background task for content processing."""
        try:
            # Update status to processing
            await self.content_repo.update(content_id, {
                "processing_status": ProcessingStatus.PROCESSING
            })

            # TODO: Implement actual AI agent processing
            # This is a placeholder for the multi-agent processing pipeline

            # 1. Store content in vector database
            await self._store_in_vector_db(content_id)

            # 2. Extract key concepts (Content Analysis Agent)
            concepts = await self._extract_concepts(content_id)

            # 3. Generate prompts (Prompt Generation Agent)
            prompts = await self._generate_prompts(content_id, concepts)

            # 4. Quality review (Quality Review Agent)
            await self._review_prompt_quality(content_id, prompts)

            # 5. Update completion status
            await self.content_repo.update(content_id, {
                "processing_status": ProcessingStatus.COMPLETED,
                "processed_at": datetime.utcnow(),
                "metadata": {
                    "concepts_extracted": len(concepts),
                    "prompts_generated": len(prompts),
                    "processing_completed_at": datetime.utcnow().isoformat()
                }
            })

        except Exception as e:
            # Update status to failed
            await self.content_repo.update(content_id, {
                "processing_status": ProcessingStatus.FAILED,
                "metadata": {
                    "error": str(e),
                    "failed_at": datetime.utcnow().isoformat()
                }
            })
            raise

    async def _store_in_vector_db(self, content_id: uuid.UUID) -> str:
        """Store content in vector database (Chroma)."""
        try:
            # Get content from database
            content = await self.content_repo.get(content_id)
            if not content:
                raise ValueError(f"Content {content_id} not found")

            collection_name = "content_embeddings"
            document_id = str(content_id)

            # Ensure collection exists
            await self.chroma_client.get_or_create_collection(
                collection_name=collection_name,
                metadata={
                    "description": "Mochi Donut content embeddings",
                    "content_type": "markdown"
                }
            )

            # Store document in Chroma with metadata
            await self.chroma_client.add_document(
                collection_name=collection_name,
                document_id=document_id,
                content=content.markdown_content,
                metadata={
                    "title": content.title,
                    "source_url": content.source_url,
                    "content_id": str(content_id),
                    "word_count": content.word_count,
                    "source_type": content.source_type.value if content.source_type else "unknown",
                    "created_at": content.created_at.isoformat()
                }
            )

            # Update content with Chroma information
            await self.content_repo.update(content_id, {
                "chroma_collection": collection_name,
                "chroma_document_id": document_id
            })

            return document_id

        except Exception as e:
            raise ValueError(f"Failed to store content in vector database: {str(e)}")

    async def _extract_concepts(self, content_id: uuid.UUID) -> List[str]:
        """Extract key concepts using Content Analysis Agent."""
        # TODO: Implement LangChain/LangGraph agent for concept extraction
        # Placeholder implementation
        content = await self.content_repo.get(content_id)
        if not content:
            raise ValueError("Content not found")

        # Mock concept extraction
        concepts = [
            "concept_1", "concept_2", "concept_3"
        ]

        return concepts

    async def _generate_prompts(
        self,
        content_id: uuid.UUID,
        concepts: List[str]
    ) -> List[str]:
        """Generate prompts using Prompt Generation Agent."""
        # TODO: Implement LangChain/LangGraph agent for prompt generation
        # Placeholder implementation

        # Mock prompt generation
        prompts = [
            f"prompt_for_{concept}" for concept in concepts
        ]

        return prompts

    async def _review_prompt_quality(
        self,
        content_id: uuid.UUID,
        prompts: List[str]
    ):
        """Review prompt quality using Quality Review Agent."""
        # TODO: Implement LangChain/LangGraph agent for quality review
        # Placeholder implementation
        pass

    async def get_processing_status(self, content_id: uuid.UUID) -> Dict[str, Any]:
        """Get detailed processing status for content."""
        content = await self.content_repo.get(content_id)
        if not content:
            raise ValueError("Content not found")

        # Get associated agent executions
        agent_executions = await self.content_repo.get_agent_executions(content_id)

        # Get prompt count
        prompt_count = await self.prompt_repo.count(content_id=content_id)

        return {
            "content_id": content_id,
            "processing_status": content.processing_status,
            "created_at": content.created_at,
            "processed_at": content.processed_at,
            "prompt_count": prompt_count,
            "agent_executions": len(agent_executions),
            "metadata": content.metadata
        }