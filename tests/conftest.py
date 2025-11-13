# Test Configuration and Fixtures for Mochi Donut
"""
pytest configuration with async testing support, database fixtures,
mock services, and test data factories for comprehensive TDD testing.
"""

import asyncio
import os
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

# Import path setup for testing
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Now import app modules
from app.core.config import Settings
from app.core.database import get_db
from app.db.models import Base, Content, Prompt, QualityMetric, AgentExecution
from app.db.models import SourceType, PromptType, ProcessingStatus, QualityMetricType, AgentType


# Test Settings
class TestSettings(Settings):
    """Test-specific configuration settings."""

    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379/1"
    ENVIRONMENT: str = "testing"
    SECRET_KEY: str = "test-secret-key-for-testing-only"

    # Disable external services for testing
    OPENAI_API_KEY: str = "test-openai-key"
    MOCHI_API_KEY: str = "test-mochi-key"
    JINA_API_KEY: str = "test-jina-key"

    # Test-specific configurations
    RATE_LIMIT_ENABLED: bool = False
    AI_CACHING_ENABLED: bool = False
    JINA_CACHE_ENABLED: bool = False


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """Provide test settings."""
    return TestSettings()


@pytest.fixture(scope="session")
async def test_engine(test_settings):
    """Create test database engine."""
    engine = create_async_engine(
        test_settings.DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def setup_database(test_engine):
    """Set up test database with tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(test_engine, setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    Session = async_sessionmaker(test_engine, expire_on_commit=False)

    async with Session() as session:
        # Start a transaction
        transaction = await session.begin()

        try:
            yield session
        finally:
            # Rollback the transaction to clean up
            await transaction.rollback()


@pytest.fixture
async def async_client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for FastAPI testing."""
    # Import here to avoid circular imports and missing dependencies
    try:
        from app.main import app

        # Override the database dependency
        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

        # Clean up
        app.dependency_overrides.clear()
    except ImportError:
        # If main app doesn't exist yet, create a minimal mock
        from fastapi import FastAPI
        from starlette.responses import JSONResponse

        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client


# Test Data Factories

@pytest.fixture
def sample_content_data():
    """Sample content data for testing."""
    return {
        "source_url": "https://example.com/article",
        "source_type": SourceType.WEB,
        "title": "Test Article",
        "author": "Test Author",
        "markdown_content": "# Test Content\n\nThis is test content for TDD testing.",
        "raw_text": "Test Content This is test content for TDD testing.",
        "content_hash": "a" * 64,  # 64-character hash
        "word_count": 10,
        "estimated_reading_time": 1,
        "processing_status": ProcessingStatus.PENDING,
        "content_metadata": {"test": True},
        "processing_config": {"max_prompts": 10}
    }


@pytest.fixture
def sample_prompt_data():
    """Sample prompt data for testing."""
    return {
        "question": "What is the main concept discussed in the test content?",
        "answer": "The main concept is TDD testing.",
        "prompt_type": PromptType.CONCEPTUAL,
        "confidence_score": 0.85,
        "difficulty_level": 3,
        "version": 1,
        "is_edited": False,
        "source_context": "Test content context",
        "tags": ["testing", "tdd"],
        "prompt_metadata": {"generated_by": "test"}
    }


@pytest.fixture
def sample_quality_metric_data():
    """Sample quality metric data for testing."""
    return {
        "metric_type": QualityMetricType.OVERALL_QUALITY,
        "score": 0.8,
        "weight": 1.0,
        "evaluator_model": "gpt-5-standard",
        "evaluation_prompt": "Rate the quality of this prompt...",
        "reasoning": "The prompt is clear and specific.",
        "feedback": {"strengths": ["clear"], "improvements": []},
        "metric_metadata": {"test": True}
    }


@pytest.fixture
def sample_agent_execution_data():
    """Sample agent execution data for testing."""
    return {
        "agent_type": AgentType.CONTENT_ANALYSIS,
        "execution_id": "test-execution-123",
        "step_number": 1,
        "status": "completed",
        "model_used": "gpt-5-nano",
        "input_tokens": 100,
        "output_tokens": 50,
        "execution_time_ms": 1500,
        "cost_usd": 0.01,
        "input_data": {"text": "test input"},
        "output_data": {"analysis": "test output"},
        "execution_metadata": {"test": True}
    }


@pytest.fixture
async def sample_content(db_session, sample_content_data) -> Content:
    """Create a sample content record in the database."""
    content = Content(**sample_content_data)
    db_session.add(content)
    await db_session.commit()
    await db_session.refresh(content)
    return content


@pytest.fixture
async def sample_prompt(db_session, sample_content, sample_prompt_data) -> Prompt:
    """Create a sample prompt record in the database."""
    prompt_data = {**sample_prompt_data, "content_id": sample_content.id}
    prompt = Prompt(**prompt_data)
    db_session.add(prompt)
    await db_session.commit()
    await db_session.refresh(prompt)
    return prompt


@pytest.fixture
async def sample_quality_metric(db_session, sample_prompt, sample_quality_metric_data) -> QualityMetric:
    """Create a sample quality metric record in the database."""
    metric_data = {**sample_quality_metric_data, "prompt_id": sample_prompt.id}
    metric = QualityMetric(**metric_data)
    db_session.add(metric)
    await db_session.commit()
    await db_session.refresh(metric)
    return metric


@pytest.fixture
async def sample_agent_execution(db_session, sample_content, sample_agent_execution_data) -> AgentExecution:
    """Create a sample agent execution record in the database."""
    execution_data = {**sample_agent_execution_data, "content_id": sample_content.id}
    execution = AgentExecution(**execution_data)
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


# Mock Services

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client


@pytest.fixture
def mock_chroma_client():
    """Mock Chroma client for testing."""
    mock_client = MagicMock()
    mock_client.create_collection = MagicMock()
    mock_client.get_collection = MagicMock()
    mock_client.add = MagicMock()
    mock_client.query = MagicMock()
    return mock_client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.set = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.exists = AsyncMock()
    return mock_client


@pytest.fixture
def mock_jina_client():
    """Mock JinaAI client for testing."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()
    return mock_client


@pytest.fixture
def mock_mochi_client():
    """Mock Mochi API client for testing."""
    mock_client = AsyncMock()
    mock_client.create_card = AsyncMock()
    mock_client.get_decks = AsyncMock()
    mock_client.update_card = AsyncMock()
    return mock_client


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    mock_task = MagicMock()
    mock_task.delay = MagicMock()
    mock_task.apply_async = MagicMock()
    mock_task.retry = MagicMock()
    return mock_task


# Test Data Collections

@pytest.fixture
def content_test_cases():
    """Comprehensive test cases for content testing."""
    return [
        {
            "name": "valid_web_content",
            "data": {
                "source_url": "https://example.com/test",
                "source_type": SourceType.WEB,
                "title": "Test Web Article",
                "author": "Web Author",
                "markdown_content": "# Web Content\n\nTest content.",
                "word_count": 3
            },
            "should_pass": True
        },
        {
            "name": "valid_pdf_content",
            "data": {
                "source_type": SourceType.PDF,
                "title": "Test PDF Document",
                "markdown_content": "# PDF Content\n\nExtracted from PDF.",
                "word_count": 4
            },
            "should_pass": True
        },
        {
            "name": "invalid_empty_content",
            "data": {
                "source_type": SourceType.WEB,
                "markdown_content": "",
            },
            "should_pass": False
        },
        {
            "name": "invalid_url_format",
            "data": {
                "source_url": "not-a-valid-url",
                "source_type": SourceType.WEB,
                "markdown_content": "# Content\n\nTest."
            },
            "should_pass": False
        }
    ]


@pytest.fixture
def prompt_test_cases():
    """Comprehensive test cases for prompt testing."""
    return [
        {
            "name": "valid_factual_prompt",
            "data": {
                "question": "What year was Python first released?",
                "answer": "Python was first released in 1991.",
                "prompt_type": PromptType.FACTUAL,
                "confidence_score": 0.9
            },
            "should_pass": True
        },
        {
            "name": "valid_conceptual_prompt",
            "data": {
                "question": "Explain the concept of recursion in programming.",
                "answer": "Recursion is when a function calls itself to solve smaller instances of the same problem.",
                "prompt_type": PromptType.CONCEPTUAL,
                "confidence_score": 0.8
            },
            "should_pass": True
        },
        {
            "name": "invalid_empty_question",
            "data": {
                "question": "",
                "answer": "Some answer",
                "prompt_type": PromptType.FACTUAL
            },
            "should_pass": False
        },
        {
            "name": "invalid_confidence_score",
            "data": {
                "question": "Test question?",
                "answer": "Test answer",
                "prompt_type": PromptType.FACTUAL,
                "confidence_score": 1.5  # Invalid: > 1.0
            },
            "should_pass": False
        }
    ]


# Utility Functions

@pytest.fixture
def assert_timestamp_recent():
    """Helper function to assert timestamps are recent."""
    def _assert_recent(timestamp: datetime, tolerance_seconds: int = 5):
        now = datetime.utcnow()
        diff = abs((now - timestamp.replace(tzinfo=None)).total_seconds())
        assert diff <= tolerance_seconds, f"Timestamp {timestamp} is not recent (diff: {diff}s)"
    return _assert_recent


@pytest.fixture
def create_test_uuid():
    """Helper function to create test UUIDs."""
    def _create_uuid():
        return uuid.uuid4()
    return _create_uuid


# Performance Testing Fixtures

@pytest.fixture
def performance_test_data():
    """Data for performance testing."""
    return {
        "content_batch_sizes": [1, 10, 50, 100],
        "prompt_batch_sizes": [5, 25, 100, 500],
        "max_response_time_ms": {
            "content_create": 1000,
            "prompt_generation": 5000,
            "quality_review": 3000,
            "api_response": 500
        }
    }


# Error Simulation Fixtures

@pytest.fixture
def error_simulation_configs():
    """Configurations for error simulation testing."""
    return {
        "database_errors": ["connection_timeout", "constraint_violation", "deadlock"],
        "external_api_errors": ["rate_limit", "timeout", "unauthorized", "service_unavailable"],
        "processing_errors": ["invalid_content", "parsing_error", "generation_failure"],
        "network_errors": ["connection_refused", "dns_failure", "ssl_error"]
    }


@pytest.fixture(autouse=True)
async def cleanup_test_data(db_session):
    """Auto-cleanup test data after each test."""
    yield
    # Cleanup is handled by transaction rollback in db_session fixture