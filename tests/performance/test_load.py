# Performance Tests - Load Testing and Benchmarks
"""
Performance tests for load testing, response time verification,
database query optimization, and system scalability testing.
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import uuid
import statistics

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.db.models import Content, Prompt, AgentExecution
from app.repositories.content import ContentRepository
from app.repositories.prompt import PromptRepository


class TestAPIPerformance:
    """Test suite for API endpoint performance."""

    @pytest.fixture
    def performance_config(self):
        """Performance test configuration."""
        return {
            "max_response_time_ms": {
                "health_check": 100,
                "content_submission": 1000,
                "content_retrieval": 500,
                "content_listing": 800,
                "prompt_operations": 600
            },
            "concurrent_users": [1, 5, 10, 20],
            "load_test_duration": 30  # seconds
        }

    async def test_health_check_response_time(self, async_client: AsyncClient, performance_config):
        """Test health check endpoint response time."""
        # Arrange
        max_time = performance_config["max_response_time_ms"]["health_check"]
        iterations = 50

        # Act - Measure response times
        response_times = []
        for _ in range(iterations):
            start_time = time.time()
            response = await async_client.get("/health")
            end_time = time.time()

            response_time_ms = (end_time - start_time) * 1000
            response_times.append(response_time_ms)

            assert response.status_code == 200

        # Assert - Performance metrics
        avg_response_time = statistics.mean(response_times)
        median_response_time = statistics.median(response_times)
        p95_response_time = sorted(response_times)[int(0.95 * len(response_times))]

        assert avg_response_time < max_time, f"Average response time {avg_response_time:.2f}ms exceeds {max_time}ms"
        assert p95_response_time < max_time * 2, f"95th percentile {p95_response_time:.2f}ms too high"

        print(f"Health check performance: avg={avg_response_time:.2f}ms, median={median_response_time:.2f}ms, p95={p95_response_time:.2f}ms")

    async def test_content_submission_performance(self, async_client: AsyncClient, performance_config):
        """Test content submission endpoint performance."""
        # Arrange
        max_time = performance_config["max_response_time_ms"]["content_submission"]
        test_content = {
            "source_type": "MARKDOWN",
            "raw_content": "# Performance Test Content\n\nThis is test content for performance testing.",
            "priority": 5
        }

        # Act - Measure submission times
        response_times = []
        for i in range(20):
            content_request = {
                **test_content,
                "raw_content": f"# Performance Test {i}\n\nTest content {i}."
            }

            start_time = time.time()
            response = await async_client.post("/api/v1/content/process", json=content_request)
            end_time = time.time()

            response_time_ms = (end_time - start_time) * 1000
            response_times.append(response_time_ms)

            assert response.status_code == 202

        # Assert
        avg_response_time = statistics.mean(response_times)
        assert avg_response_time < max_time, f"Content submission too slow: {avg_response_time:.2f}ms"

        print(f"Content submission performance: avg={avg_response_time:.2f}ms")

    async def test_content_retrieval_performance(self, async_client: AsyncClient, db_session: AsyncSession, performance_config):
        """Test content retrieval performance."""
        # Arrange - Create test content
        content_repo = ContentRepository(db_session)
        test_contents = []

        for i in range(10):
            content_data = {
                "source_type": "MARKDOWN",
                "markdown_content": f"# Test Content {i}\n\nContent for performance testing.",
                "content_hash": f"perf_test_{i}_" + "x" * 54,
                "word_count": 10,
                "estimated_reading_time": 1
            }
            content = Content(**content_data)
            db_session.add(content)
            test_contents.append(content)

        await db_session.commit()

        max_time = performance_config["max_response_time_ms"]["content_retrieval"]

        # Act - Test retrieval performance
        response_times = []
        for content in test_contents:
            start_time = time.time()
            response = await async_client.get(f"/api/v1/content/{content.id}")
            end_time = time.time()

            response_time_ms = (end_time - start_time) * 1000
            response_times.append(response_time_ms)

            assert response.status_code == 200

        # Assert
        avg_response_time = statistics.mean(response_times)
        assert avg_response_time < max_time, f"Content retrieval too slow: {avg_response_time:.2f}ms"

        print(f"Content retrieval performance: avg={avg_response_time:.2f}ms")

    async def test_content_listing_performance(self, async_client: AsyncClient, db_session: AsyncSession, performance_config):
        """Test content listing with pagination performance."""
        # Arrange - Create multiple content items
        for i in range(50):
            content_data = {
                "source_type": "MARKDOWN",
                "markdown_content": f"# Listing Test Content {i}\n\nContent for listing performance.",
                "content_hash": f"list_test_{i}_" + "x" * 54,
                "word_count": 15,
                "estimated_reading_time": 1
            }
            content = Content(**content_data)
            db_session.add(content)

        await db_session.commit()

        max_time = performance_config["max_response_time_ms"]["content_listing"]

        # Act - Test different page sizes
        page_sizes = [10, 25, 50]
        for page_size in page_sizes:
            start_time = time.time()
            response = await async_client.get(f"/api/v1/content?limit={page_size}")
            end_time = time.time()

            response_time_ms = (end_time - start_time) * 1000

            assert response.status_code == 200
            assert response_time_ms < max_time, f"Listing with {page_size} items too slow: {response_time_ms:.2f}ms"

            data = response.json()
            assert len(data["items"]) <= page_size

        print(f"Content listing performance: within {max_time}ms for all page sizes")

    async def test_concurrent_request_performance(self, async_client: AsyncClient, performance_config):
        """Test performance under concurrent load."""
        concurrent_users = performance_config["concurrent_users"]

        for user_count in concurrent_users:
            print(f"Testing with {user_count} concurrent users...")

            # Prepare requests
            tasks = []
            for i in range(user_count):
                content_request = {
                    "source_type": "MARKDOWN",
                    "raw_content": f"# Concurrent User {i}\n\nContent from user {i}.",
                    "priority": 5
                }
                task = async_client.post("/api/v1/content/process", json=content_request)
                tasks.append(task)

            # Execute concurrently and measure
            start_time = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            total_time_ms = (end_time - start_time) * 1000
            successful_responses = [r for r in responses if hasattr(r, 'status_code') and r.status_code == 202]

            # Assert
            success_rate = len(successful_responses) / len(responses)
            avg_time_per_request = total_time_ms / len(responses)

            assert success_rate >= 0.95, f"Success rate too low with {user_count} users: {success_rate:.2%}"
            assert avg_time_per_request < 2000, f"Average time per request too high: {avg_time_per_request:.2f}ms"

            print(f"  Success rate: {success_rate:.2%}, Avg time: {avg_time_per_request:.2f}ms")


class TestDatabasePerformance:
    """Test suite for database query performance."""

    async def test_content_query_performance(self, db_session: AsyncSession):
        """Test content repository query performance."""
        # Arrange - Create test data
        content_repo = ContentRepository(db_session)
        test_contents = []

        for i in range(100):
            content_data = {
                "source_type": "WEB" if i % 2 == 0 else "MARKDOWN",
                "markdown_content": f"# Query Test Content {i}\n\nContent for query performance testing.",
                "content_hash": f"query_test_{i}_" + "x" * 54,
                "word_count": 20 + (i % 50),
                "estimated_reading_time": 1 + (i % 10)
            }
            content = Content(**content_data)
            db_session.add(content)
            test_contents.append(content)

        await db_session.commit()

        # Test different query patterns
        query_tests = [
            ("get_by_id", lambda: content_repo.get(test_contents[0].id)),
            ("get_multi_no_filter", lambda: content_repo.get_multi(skip=0, limit=20)),
            ("get_multi_with_filter", lambda: content_repo.get_multi(source_type="WEB", limit=20)),
            ("count_all", lambda: content_repo.count()),
            ("count_filtered", lambda: content_repo.count(source_type="MARKDOWN")),
        ]

        # Act & Assert
        for test_name, query_func in query_tests:
            start_time = time.time()
            result = await query_func()
            end_time = time.time()

            query_time_ms = (end_time - start_time) * 1000

            # All queries should complete quickly
            assert query_time_ms < 100, f"{test_name} query too slow: {query_time_ms:.2f}ms"
            assert result is not None

            print(f"Query '{test_name}': {query_time_ms:.2f}ms")

    async def test_prompt_query_performance(self, db_session: AsyncSession, sample_content: Content):
        """Test prompt repository query performance."""
        # Arrange - Create test prompts
        prompt_repo = PromptRepository(db_session)

        for i in range(50):
            prompt_data = {
                "content_id": sample_content.id,
                "question": f"Performance test question {i}?",
                "answer": f"Performance test answer {i}.",
                "prompt_type": "FACTUAL" if i % 2 == 0 else "CONCEPTUAL",
                "confidence_score": 0.7 + (i % 3) * 0.1,
                "difficulty_level": 1 + (i % 5)
            }
            prompt = Prompt(**prompt_data)
            db_session.add(prompt)

        await db_session.commit()

        # Test prompt queries
        query_tests = [
            ("get_by_content_id", lambda: prompt_repo.get_by_content_id(sample_content.id)),
            ("get_by_prompt_type", lambda: prompt_repo.get_by_prompt_type("FACTUAL")),
            ("get_high_quality", lambda: prompt_repo.get_high_quality_prompts(min_confidence=0.8)),
            ("count_by_content", lambda: prompt_repo.count(content_id=sample_content.id)),
        ]

        # Act & Assert
        for test_name, query_func in query_tests:
            start_time = time.time()
            result = await query_func()
            end_time = time.time()

            query_time_ms = (end_time - start_time) * 1000

            assert query_time_ms < 150, f"Prompt {test_name} query too slow: {query_time_ms:.2f}ms"

            print(f"Prompt query '{test_name}': {query_time_ms:.2f}ms")

    async def test_complex_join_performance(self, db_session: AsyncSession):
        """Test performance of complex queries with joins."""
        # Arrange - Create test data with relationships
        content_data = {
            "source_type": "MARKDOWN",
            "markdown_content": "# Join Performance Test\n\nContent for testing joins.",
            "content_hash": "join_test_" + "x" * 54,
            "word_count": 25,
            "estimated_reading_time": 2
        }
        content = Content(**content_data)
        db_session.add(content)
        await db_session.flush()

        # Add prompts
        for i in range(20):
            prompt = Prompt(
                content_id=content.id,
                question=f"Join test question {i}?",
                answer=f"Join test answer {i}.",
                prompt_type="FACTUAL",
                confidence_score=0.8
            )
            db_session.add(prompt)

        # Add agent executions
        for i in range(10):
            execution = AgentExecution(
                content_id=content.id,
                agent_type="CONTENT_ANALYSIS",
                execution_id=f"join_test_{i}",
                step_number=i,
                status="completed",
                execution_time_ms=1000 + i * 100
            )
            db_session.add(execution)

        await db_session.commit()

        # Test complex queries
        complex_queries = [
            ("content_with_prompts", """
                SELECT c.*, p.id as prompt_id, p.question
                FROM contents c
                LEFT JOIN prompts p ON c.id = p.content_id
                WHERE c.id = :content_id
            """),
            ("content_with_execution_stats", """
                SELECT c.*, COUNT(ae.id) as execution_count, AVG(ae.execution_time_ms) as avg_time
                FROM contents c
                LEFT JOIN agent_executions ae ON c.id = ae.content_id
                WHERE c.id = :content_id
                GROUP BY c.id
            """),
        ]

        # Act & Assert
        for test_name, query_sql in complex_queries:
            start_time = time.time()
            result = await db_session.execute(text(query_sql), {"content_id": content.id})
            rows = result.fetchall()
            end_time = time.time()

            query_time_ms = (end_time - start_time) * 1000

            assert query_time_ms < 200, f"Complex query '{test_name}' too slow: {query_time_ms:.2f}ms"
            assert len(rows) > 0

            print(f"Complex query '{test_name}': {query_time_ms:.2f}ms, {len(rows)} rows")

    async def test_bulk_operations_performance(self, db_session: AsyncSession):
        """Test performance of bulk database operations."""
        # Test bulk insert performance
        bulk_content_data = []
        for i in range(100):
            content_data = {
                "source_type": "MARKDOWN",
                "markdown_content": f"# Bulk Content {i}\n\nBulk insert test content.",
                "content_hash": f"bulk_{i}_" + "x" * 58,
                "word_count": 15,
                "estimated_reading_time": 1
            }
            bulk_content_data.append(Content(**content_data))

        # Act - Bulk insert
        start_time = time.time()
        db_session.add_all(bulk_content_data)
        await db_session.commit()
        end_time = time.time()

        bulk_insert_time_ms = (end_time - start_time) * 1000

        # Assert
        assert bulk_insert_time_ms < 1000, f"Bulk insert too slow: {bulk_insert_time_ms:.2f}ms"

        print(f"Bulk insert of 100 records: {bulk_insert_time_ms:.2f}ms")

        # Test bulk query performance
        start_time = time.time()
        result = await db_session.execute(select(Content).limit(100))
        contents = result.scalars().all()
        end_time = time.time()

        bulk_query_time_ms = (end_time - start_time) * 1000

        assert bulk_query_time_ms < 200, f"Bulk query too slow: {bulk_query_time_ms:.2f}ms"
        assert len(contents) >= 100

        print(f"Bulk query of 100+ records: {bulk_query_time_ms:.2f}ms")


class TestMemoryAndResourcePerformance:
    """Test suite for memory usage and resource consumption."""

    async def test_memory_usage_content_processing(self, async_client: AsyncClient):
        """Test memory usage during content processing."""
        import psutil
        import os

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory_mb = process.memory_info().rss / 1024 / 1024

        # Submit multiple content items
        for i in range(20):
            large_content = {
                "source_type": "MARKDOWN",
                "raw_content": "# Large Content\n\n" + "This is a large content block. " * 1000,
                "priority": 5
            }

            response = await async_client.post("/api/v1/content/process", json=large_content)
            assert response.status_code == 202

        # Allow processing time
        await asyncio.sleep(2)

        # Check memory usage
        final_memory_mb = process.memory_info().rss / 1024 / 1024
        memory_increase_mb = final_memory_mb - initial_memory_mb

        # Assert reasonable memory usage
        assert memory_increase_mb < 100, f"Memory usage increased too much: {memory_increase_mb:.2f}MB"

        print(f"Memory usage: {initial_memory_mb:.1f}MB -> {final_memory_mb:.1f}MB (increase: {memory_increase_mb:.1f}MB)")

    async def test_database_connection_pooling(self, db_session: AsyncSession):
        """Test database connection pool performance."""
        # Simulate multiple concurrent database operations
        async def db_operation(session_num: int):
            content_data = {
                "source_type": "MARKDOWN",
                "markdown_content": f"# Pool Test {session_num}\n\nConnection pool test.",
                "content_hash": f"pool_test_{session_num}_" + "x" * 52,
                "word_count": 10,
                "estimated_reading_time": 1
            }
            content = Content(**content_data)
            db_session.add(content)
            await db_session.flush()
            return content.id

        # Execute concurrent operations
        start_time = time.time()
        tasks = [db_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        total_time_ms = (end_time - start_time) * 1000

        # Assert
        assert len(results) == 10
        assert all(result is not None for result in results)
        assert total_time_ms < 1000, f"Concurrent DB operations too slow: {total_time_ms:.2f}ms"

        print(f"10 concurrent DB operations: {total_time_ms:.2f}ms")

    async def test_api_response_size_performance(self, async_client: AsyncClient, db_session: AsyncSession):
        """Test performance with large API responses."""
        # Create content with many prompts
        content_data = {
            "source_type": "MARKDOWN",
            "markdown_content": "# Large Response Test\n\nContent for testing large responses.",
            "content_hash": "large_response_test_" + "x" * 48,
            "word_count": 50,
            "estimated_reading_time": 3
        }
        content = Content(**content_data)
        db_session.add(content)
        await db_session.flush()

        # Add many prompts
        for i in range(50):
            prompt = Prompt(
                content_id=content.id,
                question=f"Large response test question {i}? " * 10,  # Make it longer
                answer=f"Large response test answer {i}. " * 15,      # Make it longer
                prompt_type="CONCEPTUAL",
                confidence_score=0.8
            )
            db_session.add(prompt)

        await db_session.commit()

        # Test large response performance
        start_time = time.time()
        response = await async_client.get(f"/api/v1/content/{content.id}/prompts")
        end_time = time.time()

        response_time_ms = (end_time - start_time) * 1000

        # Assert
        assert response.status_code == 200
        assert response_time_ms < 1000, f"Large response too slow: {response_time_ms:.2f}ms"

        data = response.json()
        assert len(data) == 50

        response_size_kb = len(response.content) / 1024
        print(f"Large response ({response_size_kb:.1f}KB): {response_time_ms:.2f}ms")


class TestScalabilityBenchmarks:
    """Test suite for system scalability benchmarks."""

    async def test_throughput_benchmark(self, async_client: AsyncClient):
        """Benchmark system throughput under sustained load."""
        test_duration = 10  # seconds
        requests_per_second_target = 10

        start_time = time.time()
        completed_requests = 0
        failed_requests = 0

        while time.time() - start_time < test_duration:
            batch_start = time.time()

            # Submit batch of requests
            tasks = []
            for i in range(requests_per_second_target):
                request = {
                    "source_type": "MARKDOWN",
                    "raw_content": f"# Throughput Test {completed_requests + i}\n\nThroughput benchmark content.",
                    "priority": 5
                }
                tasks.append(async_client.post("/api/v1/content/process", json=request))

            # Execute batch
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Count results
            for response in responses:
                if hasattr(response, 'status_code') and response.status_code == 202:
                    completed_requests += 1
                else:
                    failed_requests += 1

            # Rate limiting
            batch_time = time.time() - batch_start
            if batch_time < 1.0:
                await asyncio.sleep(1.0 - batch_time)

        total_time = time.time() - start_time
        actual_rps = completed_requests / total_time
        error_rate = failed_requests / (completed_requests + failed_requests) if (completed_requests + failed_requests) > 0 else 0

        # Assert
        assert actual_rps >= requests_per_second_target * 0.8, f"Throughput too low: {actual_rps:.2f} RPS"
        assert error_rate < 0.05, f"Error rate too high: {error_rate:.2%}"

        print(f"Throughput benchmark: {actual_rps:.2f} RPS, {error_rate:.2%} error rate")

    async def test_stress_test_increasing_load(self, async_client: AsyncClient):
        """Test system behavior under increasing load."""
        load_levels = [1, 5, 10, 15, 20]
        performance_metrics = []

        for concurrent_requests in load_levels:
            print(f"Testing with {concurrent_requests} concurrent requests...")

            # Prepare requests
            tasks = []
            for i in range(concurrent_requests):
                request = {
                    "source_type": "MARKDOWN",
                    "raw_content": f"# Stress Test Load {concurrent_requests} Request {i}\n\nStress test content.",
                    "priority": 5
                }
                tasks.append(async_client.post("/api/v1/content/process", json=request))

            # Execute and measure
            start_time = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            # Calculate metrics
            total_time = end_time - start_time
            successful_responses = [r for r in responses if hasattr(r, 'status_code') and r.status_code == 202]
            success_rate = len(successful_responses) / len(responses)
            avg_response_time = total_time / len(responses) * 1000  # ms

            performance_metrics.append({
                "load": concurrent_requests,
                "success_rate": success_rate,
                "avg_response_time_ms": avg_response_time,
                "total_time": total_time
            })

            # System should maintain reasonable performance
            assert success_rate >= 0.9, f"Success rate dropped to {success_rate:.2%} at load {concurrent_requests}"
            assert avg_response_time < 3000, f"Response time too high: {avg_response_time:.2f}ms"

        # Print performance summary
        print("\nStress Test Results:")
        for metrics in performance_metrics:
            print(f"Load {metrics['load']:2d}: {metrics['success_rate']:.1%} success, {metrics['avg_response_time_ms']:.1f}ms avg")

    async def test_database_performance_under_load(self, db_session: AsyncSession):
        """Test database performance under concurrent load."""
        concurrent_operations = 20

        async def concurrent_db_operation(op_id: int):
            # Create content
            content = Content(
                source_type="MARKDOWN",
                markdown_content=f"# Concurrent Op {op_id}\n\nConcurrent database operation.",
                content_hash=f"concurrent_{op_id}_" + "x" * 54,
                word_count=15,
                estimated_reading_time=1
            )
            db_session.add(content)
            await db_session.flush()

            # Create prompts
            for i in range(5):
                prompt = Prompt(
                    content_id=content.id,
                    question=f"Concurrent question {op_id}-{i}?",
                    answer=f"Concurrent answer {op_id}-{i}.",
                    prompt_type="FACTUAL",
                    confidence_score=0.8
                )
                db_session.add(prompt)

            await db_session.flush()
            return content.id

        # Execute concurrent operations
        start_time = time.time()
        tasks = [concurrent_db_operation(i) for i in range(concurrent_operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        total_time = end_time - start_time
        successful_operations = [r for r in results if isinstance(r, uuid.UUID)]

        # Assert
        success_rate = len(successful_operations) / len(results)
        operations_per_second = len(successful_operations) / total_time

        assert success_rate >= 0.95, f"DB operation success rate too low: {success_rate:.2%}"
        assert operations_per_second >= 10, f"DB operations too slow: {operations_per_second:.1f} ops/sec"

        print(f"Database load test: {operations_per_second:.1f} ops/sec, {success_rate:.1%} success rate")