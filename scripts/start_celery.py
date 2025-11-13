#!/usr/bin/env python3
"""
Celery startup script for the Mochi Donut system.

Provides convenient commands for starting Celery workers and beat scheduler
with proper configuration for different environments.
"""

import argparse
import os
import sys
import subprocess
from typing import List, Optional


def run_command(cmd: List[str], env: Optional[dict] = None) -> int:
    """Run a command with optional environment variables."""
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env or os.environ, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    except Exception as e:
        print(f"Error running command: {e}")
        return 1


def start_worker(
    queues: Optional[List[str]] = None,
    concurrency: int = 4,
    loglevel: str = "info",
    max_tasks_per_child: int = 1000,
    environment: str = "development"
) -> int:
    """Start a Celery worker with specified configuration."""

    # Set environment variables
    env = os.environ.copy()
    env.update({
        "CELERY_LOG_LEVEL": loglevel.upper(),
        "ENVIRONMENT": environment,
    })

    # Base command
    cmd = [
        "uv", "run", "celery", "-A", "app.tasks",
        "worker",
        f"--loglevel={loglevel}",
        f"--concurrency={concurrency}",
        f"--max-tasks-per-child={max_tasks_per_child}",
    ]

    # Add queue specification
    if queues:
        cmd.extend(["-Q", ",".join(queues)])

    # Add environment-specific options
    if environment == "production":
        cmd.extend([
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
            "--pool=prefork",
        ])
    elif environment == "development":
        cmd.extend([
            "--pool=solo",  # Single process for development
        ])

    return run_command(cmd, env)


def start_beat(loglevel: str = "info", environment: str = "development") -> int:
    """Start Celery Beat scheduler."""

    env = os.environ.copy()
    env.update({
        "CELERY_LOG_LEVEL": loglevel.upper(),
        "ENVIRONMENT": environment,
    })

    cmd = [
        "uv", "run", "celery", "-A", "app.tasks",
        "beat",
        f"--loglevel={loglevel}",
    ]

    # Add environment-specific options
    if environment == "production":
        cmd.extend([
            "--pidfile=/tmp/celerybeat.pid",
            "--schedule=/tmp/celerybeat-schedule",
        ])

    return run_command(cmd, env)


def start_flower(port: int = 5555, environment: str = "development") -> int:
    """Start Celery Flower monitoring web interface."""

    env = os.environ.copy()
    env.update({
        "ENVIRONMENT": environment,
    })

    cmd = [
        "uv", "run", "celery", "-A", "app.tasks",
        "flower",
        f"--port={port}",
        "--broker-api=http://guest:guest@localhost:15672/api/",  # RabbitMQ management API
    ]

    if environment == "production":
        cmd.extend([
            "--basic_auth=admin:secure_password",  # Change in production
            "--url_prefix=/flower",
        ])

    return run_command(cmd, env)


def show_status() -> int:
    """Show status of Celery workers and queues."""

    print("=== Celery Worker Status ===")
    cmd = ["uv", "run", "celery", "-A", "app.tasks", "inspect", "stats"]
    run_command(cmd)

    print("\n=== Active Tasks ===")
    cmd = ["uv", "run", "celery", "-A", "app.tasks", "inspect", "active"]
    run_command(cmd)

    print("\n=== Registered Tasks ===")
    cmd = ["uv", "run", "celery", "-A", "app.tasks", "inspect", "registered"]
    run_command(cmd)

    return 0


def purge_queues(queues: Optional[List[str]] = None, force: bool = False) -> int:
    """Purge messages from queues."""

    if not force:
        confirm = input("This will delete all pending messages. Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return 0

    cmd = ["uv", "run", "celery", "-A", "app.tasks", "purge", "-f"]

    if queues:
        cmd.extend(["-Q", ",".join(queues)])

    return run_command(cmd)


def main():
    """Main command line interface."""

    parser = argparse.ArgumentParser(
        description="Celery startup and management script for Mochi Donut",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a development worker for all queues
  python start_celery.py worker

  # Start a production worker for specific queues
  python start_celery.py worker -q content_processing,ai_processing -e production -c 8

  # Start Beat scheduler
  python start_celery.py beat

  # Start Flower monitoring
  python start_celery.py flower

  # Show worker status
  python start_celery.py status

  # Purge all queues (be careful!)
  python start_celery.py purge --force
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Worker command
    worker_parser = subparsers.add_parser("worker", help="Start Celery worker")
    worker_parser.add_argument(
        "-q", "--queues",
        nargs="+",
        choices=["content_processing", "ai_processing", "external_apis", "maintenance"],
        help="Specific queues to process (default: all)"
    )
    worker_parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=4,
        help="Number of concurrent worker processes (default: 4)"
    )
    worker_parser.add_argument(
        "-l", "--loglevel",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Log level (default: info)"
    )
    worker_parser.add_argument(
        "-e", "--environment",
        choices=["development", "staging", "production"],
        default="development",
        help="Environment (default: development)"
    )
    worker_parser.add_argument(
        "--max-tasks-per-child",
        type=int,
        default=1000,
        help="Max tasks per worker child process (default: 1000)"
    )

    # Beat command
    beat_parser = subparsers.add_parser("beat", help="Start Celery Beat scheduler")
    beat_parser.add_argument(
        "-l", "--loglevel",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Log level (default: info)"
    )
    beat_parser.add_argument(
        "-e", "--environment",
        choices=["development", "staging", "production"],
        default="development",
        help="Environment (default: development)"
    )

    # Flower command
    flower_parser = subparsers.add_parser("flower", help="Start Flower monitoring")
    flower_parser.add_argument(
        "-p", "--port",
        type=int,
        default=5555,
        help="Port for Flower web interface (default: 5555)"
    )
    flower_parser.add_argument(
        "-e", "--environment",
        choices=["development", "staging", "production"],
        default="development",
        help="Environment (default: development)"
    )

    # Status command
    subparsers.add_parser("status", help="Show Celery worker status")

    # Purge command
    purge_parser = subparsers.add_parser("purge", help="Purge queue messages")
    purge_parser.add_argument(
        "-q", "--queues",
        nargs="+",
        help="Specific queues to purge (default: all)"
    )
    purge_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    if args.command == "worker":
        return start_worker(
            queues=args.queues,
            concurrency=args.concurrency,
            loglevel=args.loglevel,
            max_tasks_per_child=args.max_tasks_per_child,
            environment=args.environment
        )
    elif args.command == "beat":
        return start_beat(
            loglevel=args.loglevel,
            environment=args.environment
        )
    elif args.command == "flower":
        return start_flower(
            port=args.port,
            environment=args.environment
        )
    elif args.command == "status":
        return show_status()
    elif args.command == "purge":
        return purge_queues(
            queues=args.queues,
            force=args.force
        )
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())