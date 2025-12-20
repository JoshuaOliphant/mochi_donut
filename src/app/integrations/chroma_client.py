"""
Chroma vector database client for semantic search and content embeddings.

Provides collection management, semantic search, duplicate detection,
and embedding generation with OpenAI integration.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import os

import chromadb
from chromadb.utils import embedding_functions
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Result from semantic search operation."""
    document_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any]


class EmbeddingResult(BaseModel):
    """Result from document embedding operation."""
    document_id: str
    collection_name: str
    embedding_created_at: datetime
    metadata: Dict[str, Any]


class DuplicateCheckResult(BaseModel):
    """Result from duplicate detection."""
    is_duplicate: bool
    similar_documents: List[SearchResult]
    similarity_threshold: float


class ChromaError(Exception):
    """Base exception for Chroma client errors."""
    pass


class ChromaConnectionError(ChromaError):
    """Raised when connection to Chroma fails."""
    pass


class ChromaCollectionError(ChromaError):
    """Raised when collection operations fail."""
    pass


class ChromaClient:
    """
    Chroma vector database client with comprehensive document management.

    Features:
    - Collection management for different content types
    - Semantic search with configurable similarity thresholds
    - Duplicate detection using vector similarity
    - OpenAI embedding integration
    - Persistent storage configuration
    - Comprehensive error handling and logging
    """

    def __init__(self):
        self.client = None
        self.embedding_function = None
        self._collections: Dict[str, Any] = {}
        self._initialized = False
        self._initialization_error = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Chroma client and embedding function."""
        try:
            # Use new Chroma API (v1.x)
            if settings.is_production:
                # Production: Use Chroma Cloud with API key
                self.client = chromadb.HttpClient(
                    host=settings.CHROMA_HOST,
                    port=settings.CHROMA_PORT,
                    ssl=True,
                    headers={"Authorization": f"Bearer {settings.CHROMA_API_KEY}"}
                    if settings.CHROMA_API_KEY else None
                )
            else:
                # Development: Use local persistent storage
                persist_dir = os.path.join(os.getcwd(), "chroma_storage")
                os.makedirs(persist_dir, exist_ok=True)
                self.client = chromadb.PersistentClient(path=persist_dir)

            # Initialize OpenAI embedding function
            if not settings.OPENAI_API_KEY:
                logger.debug("OpenAI API key not provided, using default embeddings")
                self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
            else:
                self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
                    api_key=settings.OPENAI_API_KEY,
                    model_name="text-embedding-3-small"  # Cost-effective model
                )

            logger.info("Chroma client initialized successfully")
            self._initialized = True

        except Exception as e:
            logger.warning(f"Failed to initialize Chroma client: {str(e)}")
            self._initialization_error = str(e)
            self._initialized = False
            # Don't raise - allow app to start without Chroma

    async def create_collection(
        self,
        collection_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new collection in Chroma.

        Args:
            collection_name: Name of the collection
            metadata: Optional metadata for the collection

        Returns:
            Collection name

        Raises:
            ChromaCollectionError: If collection creation fails
        """
        try:
            if collection_name in self._collections:
                logger.info(f"Collection {collection_name} already exists")
                return collection_name

            collection_metadata = metadata or {}
            collection_metadata.update({
                "created_at": datetime.utcnow().isoformat(),
                "created_by": "mochi_donut"
            })

            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
                metadata=collection_metadata
            )

            self._collections[collection_name] = collection
            logger.info(f"Created collection: {collection_name}")
            return collection_name

        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {str(e)}")
            raise ChromaCollectionError(f"Failed to create collection: {str(e)}")

    async def get_or_create_collection(
        self,
        collection_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get existing collection or create new one.

        Args:
            collection_name: Name of the collection
            metadata: Optional metadata for the collection

        Returns:
            Collection name
        """
        try:
            if collection_name in self._collections:
                return collection_name

            try:
                collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                self._collections[collection_name] = collection
                logger.info(f"Retrieved existing collection: {collection_name}")
                return collection_name

            except Exception:
                # Collection doesn't exist, create it
                return await self.create_collection(collection_name, metadata)

        except Exception as e:
            logger.error(f"Failed to get or create collection {collection_name}: {str(e)}")
            raise ChromaCollectionError(f"Failed to get or create collection: {str(e)}")

    async def add_document(
        self,
        collection_name: str,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EmbeddingResult:
        """
        Add a document to a collection with automatic embedding generation.

        Args:
            collection_name: Name of the collection
            document_id: Unique identifier for the document
            content: Text content to embed
            metadata: Optional metadata for the document

        Returns:
            EmbeddingResult with operation details

        Raises:
            ChromaCollectionError: If document addition fails
        """
        try:
            # Ensure collection exists
            await self.get_or_create_collection(collection_name)
            collection = self._collections[collection_name]

            # Prepare metadata
            doc_metadata = metadata or {}
            doc_metadata.update({
                "added_at": datetime.utcnow().isoformat(),
                "content_length": len(content),
                "word_count": len(content.split())
            })

            # Add document to collection
            collection.add(
                documents=[content],
                metadatas=[doc_metadata],
                ids=[document_id]
            )

            logger.info(f"Added document {document_id} to collection {collection_name}")

            return EmbeddingResult(
                document_id=document_id,
                collection_name=collection_name,
                embedding_created_at=datetime.utcnow(),
                metadata=doc_metadata
            )

        except Exception as e:
            logger.error(f"Failed to add document {document_id}: {str(e)}")
            raise ChromaCollectionError(f"Failed to add document: {str(e)}")

    async def search_similar(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[SearchResult]:
        """
        Search for similar documents using semantic similarity.

        Args:
            collection_name: Name of the collection to search
            query_text: Text to search for
            n_results: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of SearchResult objects

        Raises:
            ChromaCollectionError: If search fails
        """
        try:
            if collection_name not in self._collections:
                await self.get_or_create_collection(collection_name)

            collection = self._collections[collection_name]

            # Perform similarity search
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )

            search_results = []
            if results["documents"] and results["documents"][0]:
                documents = results["documents"][0]
                metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(documents)
                distances = results["distances"][0] if results["distances"] else [0.0] * len(documents)
                ids = results["ids"][0] if results["ids"] else [""] * len(documents)

                for i, (doc_id, content, metadata, distance) in enumerate(zip(ids, documents, metadatas, distances)):
                    # Convert distance to similarity score (lower distance = higher similarity)
                    similarity_score = 1.0 - distance

                    # Apply similarity threshold
                    if similarity_score >= similarity_threshold:
                        search_results.append(SearchResult(
                            document_id=doc_id,
                            content=content,
                            similarity_score=similarity_score,
                            metadata=metadata or {}
                        ))

            logger.info(f"Found {len(search_results)} similar documents in {collection_name}")
            return search_results

        except Exception as e:
            logger.error(f"Failed to search collection {collection_name}: {str(e)}")
            raise ChromaCollectionError(f"Failed to search collection: {str(e)}")

    async def check_for_duplicates(
        self,
        collection_name: str,
        content: str,
        similarity_threshold: float = 0.85,
        max_results: int = 5
    ) -> DuplicateCheckResult:
        """
        Check if content is similar to existing documents (duplicate detection).

        Args:
            collection_name: Name of the collection to check
            content: Content to check for duplicates
            similarity_threshold: Threshold for considering content as duplicate
            max_results: Maximum number of similar documents to return

        Returns:
            DuplicateCheckResult with duplicate status and similar documents
        """
        try:
            similar_docs = await self.search_similar(
                collection_name=collection_name,
                query_text=content,
                n_results=max_results,
                similarity_threshold=similarity_threshold
            )

            is_duplicate = len(similar_docs) > 0

            logger.info(f"Duplicate check: {'Found' if is_duplicate else 'No'} duplicates in {collection_name}")

            return DuplicateCheckResult(
                is_duplicate=is_duplicate,
                similar_documents=similar_docs,
                similarity_threshold=similarity_threshold
            )

        except Exception as e:
            logger.error(f"Failed duplicate check in {collection_name}: {str(e)}")
            raise ChromaCollectionError(f"Failed duplicate check: {str(e)}")

    async def get_document(
        self,
        collection_name: str,
        document_id: str
    ) -> Optional[SearchResult]:
        """
        Retrieve a specific document by ID.

        Args:
            collection_name: Name of the collection
            document_id: ID of the document to retrieve

        Returns:
            SearchResult if found, None otherwise
        """
        try:
            if collection_name not in self._collections:
                await self.get_or_create_collection(collection_name)

            collection = self._collections[collection_name]

            results = collection.get(
                ids=[document_id],
                include=["documents", "metadatas"]
            )

            if results["documents"] and results["documents"]:
                return SearchResult(
                    document_id=document_id,
                    content=results["documents"][0],
                    similarity_score=1.0,  # Exact match
                    metadata=results["metadatas"][0] if results["metadatas"] else {}
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {str(e)}")
            raise ChromaCollectionError(f"Failed to get document: {str(e)}")

    async def delete_document(
        self,
        collection_name: str,
        document_id: str
    ) -> bool:
        """
        Delete a document from a collection.

        Args:
            collection_name: Name of the collection
            document_id: ID of the document to delete

        Returns:
            True if deleted successfully
        """
        try:
            if collection_name not in self._collections:
                await self.get_or_create_collection(collection_name)

            collection = self._collections[collection_name]
            collection.delete(ids=[document_id])

            logger.info(f"Deleted document {document_id} from {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {str(e)}")
            raise ChromaCollectionError(f"Failed to delete document: {str(e)}")

    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with collection statistics
        """
        try:
            if collection_name not in self._collections:
                await self.get_or_create_collection(collection_name)

            collection = self._collections[collection_name]
            count = collection.count()

            return {
                "collection_name": collection_name,
                "document_count": count,
                "collection_metadata": collection.metadata or {},
                "last_updated": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get stats for {collection_name}: {str(e)}")
            raise ChromaCollectionError(f"Failed to get collection stats: {str(e)}")

    async def list_collections(self) -> List[Dict[str, Any]]:
        """
        List all collections with their metadata.

        Returns:
            List of collection information dictionaries
        """
        try:
            collections = self.client.list_collections()
            result = []

            for collection in collections:
                stats = await self.get_collection_stats(collection.name)
                result.append(stats)

            return result

        except Exception as e:
            logger.error(f"Failed to list collections: {str(e)}")
            raise ChromaCollectionError(f"Failed to list collections: {str(e)}")

    def reset_collections_cache(self):
        """Reset the local collections cache."""
        self._collections.clear()
        logger.info("Collections cache reset")

    async def health_check(self) -> bool:
        """
        Check if Chroma client is healthy and responsive.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try to list collections as a health check
            self.client.list_collections()
            return True
        except Exception as e:
            logger.error(f"Chroma health check failed: {str(e)}")
            return False


# Global Chroma client instance
chroma_client = ChromaClient()