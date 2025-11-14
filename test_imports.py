#!/usr/bin/env python
# ABOUTME: Validates all Python module imports and checks for circular dependencies
# ABOUTME: Reports on accessibility of key functions and classes

import sys
import traceback
from pathlib import Path
from typing import List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


class ImportValidator:
    """Validates imports and generates a detailed test report."""

    def __init__(self):
        self.results = []
        self.successes = []
        self.failures = []

    def test_import(self, module_path: str) -> Tuple[bool, str]:
        """Test importing a single module."""
        try:
            __import__(module_path)
            return True, f"✅ {module_path}"
        except Exception as e:
            error_msg = f"❌ {module_path}\n   Error: {str(e)}"
            return False, error_msg

    def test_class_accessibility(
        self, module_path: str, class_name: str
    ) -> Tuple[bool, str]:
        """Test that a specific class is accessible."""
        try:
            module = __import__(module_path, fromlist=[class_name])
            getattr(module, class_name)
            return True, f"✅ {module_path}.{class_name}"
        except Exception as e:
            error_msg = f"❌ {module_path}.{class_name}\n   Error: {str(e)}"
            return False, error_msg

    def test_function_accessibility(
        self, module_path: str, function_name: str
    ) -> Tuple[bool, str]:
        """Test that a specific function is accessible."""
        try:
            module = __import__(module_path, fromlist=[function_name])
            getattr(module, function_name)
            return True, f"✅ {module_path}.{function_name}()"
        except Exception as e:
            error_msg = f"❌ {module_path}.{function_name}()\n   Error: {str(e)}"
            return False, error_msg

    def run_all_tests(self):
        """Run all import validation tests."""
        print("\n" + "=" * 80)
        print("MOCHI DONUT - IMPORT VALIDATION TEST SUITE")
        print("=" * 80 + "\n")

        # Test 1: Core module imports
        print("TEST 1: Core Module Imports")
        print("-" * 80)
        core_modules = [
            "src.app.main",
            "src.app.db.models",
            "src.app.db.config",
            "src.app.core.config",
            "src.app.core.database",
            "src.app.schemas.content",
            "src.app.schemas.prompt",
            "src.app.schemas.common",
            "src.app.schemas.claude_workflow",
            "src.app.agents.subagents",
            "src.app.agents.config",
            "src.app.agents.base",
            "src.app.agents.orchestrator",
            "src.app.agents.content_analyzer",
            "src.app.agents.prompt_generator",
            "src.app.agents.quality_reviewer",
            "src.app.agents.refinement_agent",
            "src.app.agents.workflow",
            "src.app.agents.service",
            "src.app.mcp_tools",
            "src.app.mcp_tools.jina",
            "src.app.mcp_tools.chroma",
            "src.app.mcp_tools.mochi",
            "src.app.mcp_tools.database",
            "src.app.services.content_processor",
            "src.app.services.prompt_service",
            "src.app.services.search_service",
            "src.app.api.v1.endpoints.process",
            "src.app.api.v1.endpoints.prompts",
            "src.app.api.v1.endpoints.content",
            "src.app.api.v1.endpoints.search",
            "src.app.api.v1.endpoints.analytics",
            "src.app.web.routes",
            "src.app.repositories.content",
            "src.app.repositories.prompt",
            "src.app.integrations.jina_client",
            "src.app.integrations.chroma_client",
            "src.app.integrations.mochi_client",
        ]

        for module in core_modules:
            success, message = self.test_import(module)
            print(message)
            if success:
                self.successes.append(module)
            else:
                self.failures.append((module, message))

        # Test 2: Key functions accessibility
        print("\n\nTEST 2: Key Function Accessibility")
        print("-" * 80)
        functions = [
            ("src.app.agents.subagents", "get_subagent_definitions"),
            ("src.app.mcp_tools", "get_all_tools"),
        ]

        for module_path, func_name in functions:
            success, message = self.test_function_accessibility(module_path, func_name)
            print(message)
            if success:
                self.successes.append(f"{module_path}.{func_name}")
            else:
                self.failures.append((f"{module_path}.{func_name}", message))

        # Test 3: Key classes accessibility
        print("\n\nTEST 3: Key Class Accessibility")
        print("-" * 80)
        classes = [
            ("src.app.services.content_processor", "ContentProcessorService"),
            ("src.app.schemas.content", "ContentCreate"),
            ("src.app.schemas.prompt", "PromptCreate"),
            ("src.app.agents.orchestrator", "OrchestratorAgent"),
            ("src.app.repositories.content", "ContentRepository"),
            ("src.app.repositories.prompt", "PromptRepository"),
        ]

        for module_path, class_name in classes:
            success, message = self.test_class_accessibility(module_path, class_name)
            print(message)
            if success:
                self.successes.append(f"{module_path}.{class_name}")
            else:
                self.failures.append((f"{module_path}.{class_name}", message))

        # Summary
        print("\n\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"✅ Passed: {len(self.successes)}")
        print(f"❌ Failed: {len(self.failures)}")

        if self.failures:
            print("\n" + "-" * 80)
            print("FAILED IMPORTS:")
            print("-" * 80)
            for module, error in self.failures:
                print(f"\n{error}")

        # Overall result
        print("\n" + "=" * 80)
        if not self.failures:
            print("✅ ALL TESTS PASSED - All imports successful!")
        else:
            print(f"❌ TESTS FAILED - {len(self.failures)} import(s) failed")
        print("=" * 80 + "\n")

        return len(self.failures) == 0


if __name__ == "__main__":
    validator = ImportValidator()
    success = validator.run_all_tests()
    sys.exit(0 if success else 1)
