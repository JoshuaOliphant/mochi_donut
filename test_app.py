#!/usr/bin/env python
"""
Simple test script to verify the FastAPI application starts correctly.
Run with: uv run python test_app.py
"""

import asyncio
import httpx
from src.app.main import app
from src.app.core.database import db


async def test_endpoints():
    """Test basic API endpoints."""
    print("🚀 Starting Mochi Donut API Test...")

    # Initialize database
    print("📦 Initializing database...")
    await db.init_db()

    # Test endpoints
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Test health endpoint
        print("\n✅ Testing health endpoint...")
        response = await client.get("/api/v1/health")
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")

        # Test detailed health
        print("\n📊 Testing detailed health...")
        response = await client.get("/api/v1/health/detailed")
        print(f"Detailed health: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Database: {data['database']}")
            print(f"Environment: {data['environment']}")

        # Test content endpoints
        print("\n📝 Testing content endpoints...")

        # List content (should be empty)
        response = await client.get("/api/v1/content")
        print(f"List content: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Total items: {data['total']}")

        # Create test content
        print("\n➕ Creating test content...")
        test_content = {
            "source_url": "https://example.com/article",
            "source_type": "web",
            "title": "Test Article",
            "markdown_content": "# Test Article\n\nThis is a test article about spaced repetition learning."
        }
        response = await client.post("/api/v1/content", json=test_content)
        print(f"Create content: {response.status_code}")
        if response.status_code == 201:
            content = response.json()
            content_id = content['id']
            print(f"Created content ID: {content_id}")

            # Get the created content
            response = await client.get(f"/api/v1/content/{content_id}")
            print(f"Get content: {response.status_code}")

            # Test prompt generation
            print("\n🤖 Testing prompt generation...")
            response = await client.post(
                f"/api/v1/prompts/generate/{content_id}",
                json={"count": 5, "types": ["factual", "conceptual"]}
            )
            print(f"Generate prompts: {response.status_code}")

            # List prompts for content
            response = await client.get(f"/api/v1/prompts/content/{content_id}")
            print(f"List prompts: {response.status_code}")
            if response.status_code == 200:
                prompts = response.json()
                print(f"Generated prompts: {len(prompts)} (placeholder)")

    # Close database connection
    await db.close()

    print("\n✅ All tests completed successfully!")


if __name__ == "__main__":
    print("=" * 50)
    print("MOCHI DONUT API TEST")
    print("=" * 50)
    asyncio.run(test_endpoints())