# ABOUTME: pytest configuration for Mochi Donut MCP server tests
# ABOUTME: Minimal fixtures for testing the MCP server
"""
Pytest configuration for Mochi Donut tests.

Provides common fixtures for testing the MCP server components.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure src is in path for imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure clean environment for each test."""
    # Remove any existing API keys to ensure tests are isolated
    monkeypatch.delenv("MOCHI_API_KEY", raising=False)


@pytest.fixture
def mock_mochi_key(monkeypatch):
    """Set a mock Mochi API key."""
    monkeypatch.setenv("MOCHI_API_KEY", "test-api-key-12345")
