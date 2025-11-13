# ABOUTME: MCP tools for database operations
# ABOUTME: Saves and queries content and prompts using async SQLAlchemy
"""MCP tools for database operations."""

from claude_agent_sdk import tool
from typing import Dict, Any, List
from sqlalchemy import select
from src.app.core.database import db
from src.app.db.models import Content, Prompt, QualityMetric
import uuid


@tool(
    name="save_content",
    description="Save processed content to database",
    input_schema={
        "content_id": str,
        "source_url": str,
        "markdown": str,
        "metadata": dict
    }
)
async def save_content(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save content to database.

    Args:
        args: {
            "content_id": "uuid-string",
            "source_url": "https://...",
            "markdown": "markdown content",
            "metadata": {"title": "...", "author": "..."}
        }
    """
    try:
        async with db.async_session() as session:
            # Generate content hash from markdown
            import hashlib
            content_hash = hashlib.sha256(args["markdown"].encode()).hexdigest()

            # Extract metadata fields
            metadata = args.get("metadata", {})

            content = Content(
                id=uuid.UUID(args["content_id"]),
                source_url=args["source_url"],
                source_type="web",  # Default to web, can be parameterized
                title=metadata.get("title"),
                author=metadata.get("author"),
                markdown_content=args["markdown"],
                content_hash=content_hash,
                content_metadata=metadata,
                processing_status="completed"
            )
            session.add(content)
            await session.commit()

            return {
                "content": [{
                    "type": "text",
                    "text": f"Saved content to database: {args['content_id']}"
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error saving content: {str(e)}"
            }],
            "isError": True
        }


@tool(
    name="save_prompts",
    description="Save generated prompts to database",
    input_schema={
        "content_id": str,
        "prompts": list  # List of prompt objects
    }
)
async def save_prompts(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save generated prompts to database.

    Args:
        args: {
            "content_id": "uuid-string",
            "prompts": [
                {
                    "question": "...",
                    "answer": "...",
                    "prompt_type": "factual",
                    "difficulty_level": 3,
                    "confidence_score": 0.85,
                    "source_context": "..."
                }
            ]
        }
    """
    try:
        async with db.async_session() as session:
            prompt_ids = []

            for p in args["prompts"]:
                prompt = Prompt(
                    id=uuid.uuid4(),
                    content_id=uuid.UUID(args["content_id"]),
                    question=p["question"],
                    answer=p["answer"],
                    prompt_type=p["prompt_type"],
                    difficulty_level=p.get("difficulty_level"),
                    confidence_score=p.get("confidence_score"),
                    source_context=p.get("source_context")
                )
                session.add(prompt)
                prompt_ids.append(str(prompt.id))

            await session.commit()

            return {
                "content": [{
                    "type": "text",
                    "text": f"Saved {len(prompt_ids)} prompts to database"
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error saving prompts: {str(e)}"
            }],
            "isError": True
        }


@tool(
    name="query_prompts",
    description="Query database for prompts by various criteria",
    input_schema={
        "content_id": str,
        "status": str,
        "limit": int
    }
)
async def query_prompts(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query prompts from database.

    Args:
        args: {
            "content_id": "uuid-string" (optional),
            "status": "pending" (optional),
            "limit": 10
        }
    """
    try:
        async with db.async_session() as session:
            query = select(Prompt)

            if args.get("content_id"):
                query = query.where(Prompt.content_id == uuid.UUID(args["content_id"]))

            # Note: status filtering would require PromptStatus field
            # which isn't in the current Prompt model

            query = query.limit(args.get("limit", 10))

            result = await session.execute(query)
            prompts = result.scalars().all()

            formatted_prompts = [
                {
                    "id": str(p.id),
                    "question": p.question[:100] + "..." if len(p.question) > 100 else p.question,
                    "prompt_type": p.prompt_type.value,
                    "confidence_score": p.confidence_score
                }
                for p in prompts
            ]

            return {
                "content": [{
                    "type": "text",
                    "text": f"Found {len(prompts)} prompts:\n" +
                           "\n".join([f"- {p['question']} ({p['prompt_type']})"
                                     for p in formatted_prompts])
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error querying prompts: {str(e)}"
            }],
            "isError": True
        }


@tool(
    name="update_prompt_status",
    description="Update the status of a prompt",
    input_schema={
        "prompt_id": str,
        "mochi_card_id": str,
        "mochi_deck_id": str
    }
)
async def update_prompt_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update prompt with Mochi card information.

    Args:
        args: {
            "prompt_id": "uuid-string",
            "mochi_card_id": "mochi-card-id",
            "mochi_deck_id": "mochi-deck-id"
        }
    """
    try:
        async with db.async_session() as session:
            query = select(Prompt).where(Prompt.id == uuid.UUID(args["prompt_id"]))
            result = await session.execute(query)
            prompt = result.scalar_one_or_none()

            if not prompt:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Prompt {args['prompt_id']} not found"
                    }],
                    "isError": True
                }

            prompt.mochi_card_id = args.get("mochi_card_id")
            prompt.mochi_deck_id = args.get("mochi_deck_id")
            prompt.mochi_status = "sent"

            await session.commit()

            return {
                "content": [{
                    "type": "text",
                    "text": f"Updated prompt {args['prompt_id']} with Mochi card info"
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error updating prompt status: {str(e)}"
            }],
            "isError": True
        }
