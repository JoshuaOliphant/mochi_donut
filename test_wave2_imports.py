#!/usr/bin/env python3
"""
ABOUTME: Wave 2 Integration Test 4 - Comprehensive import verification
ABOUTME: Validates all 41 modules import successfully with SECRET_KEY set, confirms LangChain removal

This test script:
1. Sets SECRET_KEY environment variable before any imports
2. Attempts to import all 41 modules from Wave 1
3. Tests specific imports that previously failed
4. Verifies NO LangChain imports exist
5. Reports detailed pass/fail results
"""

import os
import sys
import subprocess
from pathlib import Path

# CRITICAL: Set SECRET_KEY BEFORE any app imports
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ENVIRONMENT"] = "testing"

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Test modules - all 41 from Wave 1 test list
TEST_MODULES = [
    # Core configuration
    "app.core.config",
    "app.core.database",

    # Database layer
    "app.db.models",
    "app.db.config",
    "app.db.utils",
    "app.db.performance",

    # Schemas
    "app.schemas.common",
    "app.schemas.content",
    "app.schemas.prompt",
    "app.schemas.claude_workflow",

    # Repositories
    "app.repositories.base",
    "app.repositories.content",
    "app.repositories.prompt",

    # Services
    "app.services.content_processor",
    "app.services.prompt_generator",
    "app.services.prompt_service",
    "app.services.search_service",

    # API
    "app.api.dependencies",
    "app.api.task_endpoints",
    "app.api.v1.router",
    "app.api.v1.endpoints.content",
    "app.api.v1.endpoints.search",
    "app.api.v1.endpoints.analytics",
    "app.api.v1.endpoints.monitoring",
    "app.api.v1.endpoints.process",
    "app.api.v1.endpoints.prompts",

    # Integrations
    "app.integrations.dependencies",
    "app.integrations.jina_client",
    "app.integrations.chroma_client",
    "app.integrations.mochi_client",

    # Agents
    "app.agents.subagents",

    # Tasks
    "app.tasks.celery_app",
    "app.tasks.content_tasks",
    "app.tasks.sync_tasks",
    "app.tasks.monitoring",
    "app.tasks.task_utils",
    "app.tasks.maintenance_tasks",

    # MCP Tools
    "app.mcp_tools.jina",
    "app.mcp_tools.chroma",
    "app.mcp_tools.mochi",
    "app.mcp_tools.database",

    # Main app
    "app.main",
]

# Special imports to test
SPECIAL_IMPORTS = [
    ("app.core.config", "Settings"),
    ("app.repositories.base", "BaseRepository"),
    ("app.db.models", "Content"),
    ("app.services.content_processor", "ContentProcessorService"),
]

def print_header(text):
    """Print a formatted header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def test_module_import(module_name):
    """Test importing a single module"""
    try:
        __import__(module_name)
        return True, None
    except Exception as e:
        return False, str(e)

def test_special_import(module_name, class_name):
    """Test importing a specific class from a module"""
    try:
        module = __import__(module_name, fromlist=[class_name])
        getattr(module, class_name)
        return True, None
    except Exception as e:
        return False, str(e)

def check_langchain_imports():
    """Check if any LangChain imports exist in src/"""
    src_path = Path(__file__).parent / "src"

    # Check for 'from langchain' imports
    result1 = subprocess.run(
        ["grep", "-r", "from langchain", "src/", "--include=*.py"],
        capture_output=True,
        text=True
    )

    # Check for 'import langchain' imports
    result2 = subprocess.run(
        ["grep", "-r", "import langchain", "src/", "--include=*.py"],
        capture_output=True,
        text=True
    )

    from_langchain = result1.stdout.strip().split('\n') if result1.stdout.strip() else []
    import_langchain = result2.stdout.strip().split('\n') if result2.stdout.strip() else []

    # Filter out empty strings
    from_langchain = [line for line in from_langchain if line]
    import_langchain = [line for line in import_langchain if line]

    return from_langchain, import_langchain

def main():
    """Run the comprehensive import test"""
    print_header("WAVE 2 INTEGRATION TEST 4: IMPORT VERIFICATION")

    # Print environment info
    print(f"SECRET_KEY set: {bool(os.environ.get('SECRET_KEY'))}")
    print(f"ENVIRONMENT: {os.environ.get('ENVIRONMENT')}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Working directory: {Path.cwd()}")

    # Test regular module imports
    print_header("PHASE 1: TESTING MODULE IMPORTS (41 modules)")

    passed = 0
    failed = 0
    failures = []

    for module_name in TEST_MODULES:
        success, error = test_module_import(module_name)
        if success:
            print(f"✅ {module_name}")
            passed += 1
        else:
            print(f"❌ {module_name}")
            print(f"   Error: {error}")
            failed += 1
            failures.append((module_name, error))

    print_header(f"MODULE IMPORT RESULTS: {passed}/41 PASSED")

    if failed > 0:
        print(f"⚠️  {failed} modules failed to import:\n")
        for module_name, error in failures:
            print(f"  • {module_name}")
            print(f"    {error[:100]}...")
    else:
        print("✅ ALL 41 MODULES IMPORTED SUCCESSFULLY!")

    # Test special imports
    print_header("PHASE 2: TESTING SPECIAL CLASS IMPORTS")

    special_passed = 0
    special_failed = 0
    special_failures = []

    for module_name, class_name in SPECIAL_IMPORTS:
        success, error = test_special_import(module_name, class_name)
        if success:
            print(f"✅ {module_name}.{class_name}")
            special_passed += 1
        else:
            print(f"❌ {module_name}.{class_name}")
            print(f"   Error: {error}")
            special_failed += 1
            special_failures.append((f"{module_name}.{class_name}", error))

    print_header(f"SPECIAL IMPORTS RESULTS: {special_passed}/{len(SPECIAL_IMPORTS)} PASSED")

    if special_failed > 0:
        print(f"⚠️  {special_failed} special imports failed:\n")
        for import_name, error in special_failures:
            print(f"  • {import_name}")
    else:
        print("✅ ALL SPECIAL IMPORTS SUCCESSFUL!")

    # Check for LangChain imports
    print_header("PHASE 3: LANGCHAIN REMOVAL VERIFICATION")

    from_langchain, import_langchain = check_langchain_imports()

    print(f"Checking for 'from langchain' imports...")
    if from_langchain:
        print(f"❌ FOUND {len(from_langchain)} 'from langchain' imports:")
        for line in from_langchain[:10]:  # Show first 10
            print(f"  • {line}")
        if len(from_langchain) > 10:
            print(f"  ... and {len(from_langchain) - 10} more")
    else:
        print(f"✅ NO 'from langchain' imports found")

    print(f"\nChecking for 'import langchain' imports...")
    if import_langchain:
        print(f"❌ FOUND {len(import_langchain)} 'import langchain' imports:")
        for line in import_langchain[:10]:  # Show first 10
            print(f"  • {line}")
        if len(import_langchain) > 10:
            print(f"  ... and {len(import_langchain) - 10} more")
    else:
        print(f"✅ NO 'import langchain' imports found")

    # Final summary
    print_header("FINAL RESULTS")

    total_langchain_issues = len(from_langchain) + len(import_langchain)
    all_imports_passed = failed == 0 and special_failed == 0
    langchain_clean = total_langchain_issues == 0

    print(f"Module imports: {passed}/41 ({100*passed//41}%)")
    print(f"Special imports: {special_passed}/{len(SPECIAL_IMPORTS)} ({100*special_passed//len(SPECIAL_IMPORTS)}%)")
    print(f"LangChain references: {total_langchain_issues} found")

    if all_imports_passed and langchain_clean:
        print("\n🎉 SUCCESS! All Wave 1 fixes verified!")
        print("   ✅ 41/41 modules imported successfully")
        print("   ✅ All special imports working")
        print("   ✅ No LangChain references found")
        return 0
    else:
        print("\n⚠️  TEST FAILED - Issues detected:")
        if failed > 0:
            print(f"   ❌ {failed} module import failures")
        if special_failed > 0:
            print(f"   ❌ {special_failed} special import failures")
        if total_langchain_issues > 0:
            print(f"   ❌ {total_langchain_issues} LangChain references found")
        return 1

if __name__ == "__main__":
    sys.exit(main())
