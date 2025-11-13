# ABOUTME: MCP tools for Chroma vector database integration
# ABOUTME: Stores and searches content with embeddings using Chroma DB
"""MCP tools for Chroma vector database integration."""

import chromadb
from chromadb.config import Settings
from claude_agent_sdk import tool
from typing import Dict, Any, List, Optional

# Initialize Chroma client (singleton)
_chroma_client: Optional[chromadb.Client] = None


def get_chroma_client() -> chromadb.Client:
    """Get or create singleton Chroma client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.Client(Settings(
            persist_directory="./chroma_data",
            anonymized_telemetry=False
        ))
    return _chroma_client


@tool(
    name="store_content",
    description="Store content in Chroma vector database with embeddings",
    input_schema={
        "content_id": str,
        "text": str,
        "metadata": dict
    }
)
async def store_content(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Store content in Chroma with automatic embedding generation.

    Args:
        args: {
            "content_id": "uuid-string",
            "text": "markdown content",
            "metadata": {"url": "...", "title": "..."}
        }
    """
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(
            name="mochi_donut_content",
            metadata={"description": "Processed content for flashcard generation"}
        )

        # Store with automatic embedding
        collection.add(
            documents=[args["text"]],
            metadatas=[args["metadata"]],
            ids=[args["content_id"]]
        )

        return {
            "content": [{
                "type": "text",
                "text": f"Stored content {args['content_id']} in Chroma"
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error storing in Chroma: {str(e)}"
            }],
            "isError": True
        }


@tool(
    name="search_similar",
    description="Search for similar content in Chroma vector database",
    input_schema={
        "query": str,
        "n_results": int
    }
)
async def search_similar(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for semantically similar content.

    Args:
        args: {
            "query": "search query text",
            "n_results": 5
        }
    """
    try:
        client = get_chroma_client()
        collection = client.get_collection("mochi_donut_content")

        results = collection.query(
            query_texts=[args["query"]],
            n_results=args.get("n_results", 5)
        )

        # Format results
        formatted = []
        for i, doc in enumerate(results['documents'][0]):
            metadata = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            formatted.append({
                "content": doc[:200] + "...",
                "metadata": metadata,
                "similarity": 1 - distance  # Convert distance to similarity
            })

        return {
            "content": [{
                "type": "text",
                "text": f"Found {len(formatted)} similar documents:\n" +
                       "\n".join([f"- {r['metadata'].get('title', 'Untitled')} (similarity: {r['similarity']:.2f})"
                                 for r in formatted])
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error searching Chroma: {str(e)}"
            }],
            "isError": True
        }
