#!/usr/bin/env python3
"""Wave 2 Database Integration Test: Verify migrations and schema initialization"""

import os
import sys
import sqlite3
import asyncio
from pathlib import Path
from subprocess import run, PIPE

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set test environment variables BEFORE importing app modules
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ENVIRONMENT"] = "testing"

# Use test.db in the repo root
test_db_path = Path(__file__).parent / "test_wave2.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path}"


def cleanup_test_db():
    """Remove any existing test database file."""
    test_db_path.unlink(missing_ok=True)
    print(f"✓ Cleaned up test database: {test_db_path}")


def run_migrations(direction: str = "upgrade", target: str = "head") -> bool:
    """
    Execute Alembic migrations.

    Args:
        direction: Either "upgrade" or "downgrade"
        target: Target revision (e.g., "head" or "-1")

    Returns:
        True if successful, False otherwise
    """
    cmd = ["alembic", direction, target]
    result = run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).parent))

    if result.returncode != 0:
        print(f"✗ Migration failed ({direction} {target}):")
        print(f"  STDOUT: {result.stdout}")
        print(f"  STDERR: {result.stderr}")
        return False

    print(f"✓ Migration successful: alembic {direction} {target}")
    return True


def verify_table_exists(db_path: Path, table_name: str) -> bool:
    """Verify a table exists in the SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        exists = cursor.fetchone() is not None
        conn.close()

        status = "✓" if exists else "✗"
        print(f"{status} Table '{table_name}': {'exists' if exists else 'NOT FOUND'}")
        return exists
    except Exception as e:
        print(f"✗ Error checking table '{table_name}': {e}")
        return False


def verify_column_exists(db_path: Path, table_name: str, column_name: str) -> bool:
    """Verify a column exists in a table."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        exists = column_name in columns
        status = "✓" if exists else "✗"
        print(f"{status} Column '{table_name}.{column_name}': {'exists' if exists else 'NOT FOUND'}")
        return exists
    except Exception as e:
        print(f"✗ Error checking column '{column_name}' in '{table_name}': {e}")
        return False


def verify_index_exists(db_path: Path, index_name: str) -> bool:
    """Verify an index exists in the database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,)
        )
        exists = cursor.fetchone() is not None
        conn.close()

        status = "✓" if exists else "✗"
        print(f"{status} Index '{index_name}': {'exists' if exists else 'NOT FOUND'}")
        return exists
    except Exception as e:
        print(f"✗ Error checking index '{index_name}': {e}")
        return False


def get_column_info(db_path: Path, table_name: str, column_name: str) -> dict:
    """Get detailed column information."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        for row in cursor.fetchall():
            if row[1] == column_name:
                conn.close()
                return {
                    "name": row[1],
                    "type": row[2],
                    "not_null": row[3],
                    "default": row[4],
                    "pk": row[5]
                }
        conn.close()
        return None
    except Exception as e:
        print(f"✗ Error getting column info: {e}")
        return None


def main():
    """Execute all database integration tests."""
    print("=" * 70)
    print("Wave 2 Database Integration Test")
    print("=" * 70)
    print()

    results = {
        "cleanup": False,
        "migrate_up": False,
        "tables_exist": False,
        "status_column": False,
        "status_index": False,
        "migrate_down": False,
        "migrate_up_again": False,
    }

    # Step 1: Clean up test database
    print("Step 1: Clean up test database")
    print("-" * 70)
    cleanup_test_db()
    results["cleanup"] = True
    print()

    # Step 2: Run migrations (upgrade head)
    print("Step 2: Apply all migrations")
    print("-" * 70)
    results["migrate_up"] = run_migrations("upgrade", "head")
    print()

    if not results["migrate_up"]:
        print("✗ FATAL: Initial migration failed. Cannot continue.")
        return results

    # Step 3: Verify all tables exist
    print("Step 3: Verify critical tables exist")
    print("-" * 70)
    tables_to_check = ["contents", "prompts", "quality_metrics", "agent_executions", "user_interactions", "processing_queue"]
    table_results = all(verify_table_exists(test_db_path, table) for table in tables_to_check)
    results["tables_exist"] = table_results
    print()

    # Step 4: Verify Prompt.status column exists (Wave 1 critical fix)
    print("Step 4: Verify Prompt.status column (Critical - Wave 1 fix)")
    print("-" * 70)
    status_col_exists = verify_column_exists(test_db_path, "prompts", "status")

    if status_col_exists:
        col_info = get_column_info(test_db_path, "prompts", "status")
        if col_info:
            print(f"  Column details:")
            print(f"    Type: {col_info['type']}")
            print(f"    Not Null: {col_info['not_null']}")
            print(f"    Default: {col_info['default']}")

    results["status_column"] = status_col_exists
    print()

    # Step 5: Verify status index exists
    print("Step 5: Verify index on Prompt.status column")
    print("-" * 70)
    results["status_index"] = verify_index_exists(test_db_path, "ix_prompt_status")
    print()

    # Step 6: Test migration rollback
    print("Step 6: Test migration rollback (downgrade -1)")
    print("-" * 70)
    results["migrate_down"] = run_migrations("downgrade", "-1")

    if results["migrate_down"]:
        # Verify status column is gone after downgrade
        status_col_after_down = verify_column_exists(test_db_path, "prompts", "status")
        if status_col_after_down:
            print("✗ WARNING: status column still exists after downgrade!")
        else:
            print("✓ Verified: status column removed after downgrade")
    print()

    # Step 7: Test migration forward again
    print("Step 7: Test migration upgrade again (upgrade head)")
    print("-" * 70)
    results["migrate_up_again"] = run_migrations("upgrade", "head")

    if results["migrate_up_again"]:
        # Verify status column is restored
        status_col_after_up = verify_column_exists(test_db_path, "prompts", "status")
        if status_col_after_up:
            print("✓ Verified: status column restored after upgrade")
        else:
            print("✗ ERROR: status column missing after upgrade!")
    print()

    # Summary Report
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    test_names = [
        ("Database cleanup", results["cleanup"]),
        ("Migration upgrade (initial)", results["migrate_up"]),
        ("All tables exist", results["tables_exist"]),
        ("Prompt.status column exists", results["status_column"]),
        ("Prompt.status index exists", results["status_index"]),
        ("Migration rollback works", results["migrate_down"]),
        ("Migration upgrade works (again)", results["migrate_up_again"]),
    ]

    print()
    for test_name, passed in test_names:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())
    print()
    print("=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED - Database migrations working correctly!")
    else:
        print("✗ SOME TESTS FAILED - Review output above")
    print("=" * 70)

    # Cleanup test database after tests
    print()
    print("Cleaning up test database...")
    cleanup_test_db()

    return results


if __name__ == "__main__":
    results = main()

    # Exit with success only if all tests passed
    sys.exit(0 if all(results.values()) else 1)
