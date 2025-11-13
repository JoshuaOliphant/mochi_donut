#!/bin/bash

# Database migration script for Mochi Donut production
# Handles safe migrations with backup and rollback capabilities

set -euo pipefail

# Configuration
APP_NAME="mochi-donut"
BACKUP_DIR="./migration_backups"
DB_PATH="/data/mochi_donut.db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v flyctl &> /dev/null; then
        log_error "flyctl is not installed"
        exit 1
    fi

    if ! flyctl auth whoami &> /dev/null; then
        log_error "Not authenticated with Fly.io"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Create backup before migration
create_backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/pre_migration_backup_$timestamp.db"

    mkdir -p "$BACKUP_DIR"

    log_info "Creating pre-migration backup..."

    if flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH .backup /tmp/backup.db" && \
       flyctl ssh sftp --app "$APP_NAME" get /tmp/backup.db "$backup_file"; then
        gzip "$backup_file"
        log_success "Backup created: ${backup_file}.gz"
        echo "$backup_file.gz"  # Return backup file path
    else
        log_error "Failed to create backup"
        exit 1
    fi
}

# Check current migration status
check_migration_status() {
    log_info "Checking current migration status..."

    # Get current revision
    local current_revision
    current_revision=$(flyctl ssh console --app "$APP_NAME" --command "cd /app && uv run alembic current" 2>/dev/null | tail -1 || echo "unknown")

    # Get latest revision
    local latest_revision
    latest_revision=$(flyctl ssh console --app "$APP_NAME" --command "cd /app && uv run alembic heads" 2>/dev/null | tail -1 || echo "unknown")

    echo "Current revision: $current_revision"
    echo "Latest revision: $latest_revision"

    if [ "$current_revision" = "$latest_revision" ]; then
        log_info "Database is up to date"
        return 0
    else
        log_warning "Database needs migration"
        return 1
    fi
}

# Show pending migrations
show_pending_migrations() {
    log_info "Pending migrations:"

    flyctl ssh console --app "$APP_NAME" --command "cd /app && uv run alembic history --verbose" | grep -A 5 -B 5 "Rev:"
}

# Validate migration scripts
validate_migrations() {
    log_info "Validating migration scripts..."

    # Check for syntax errors
    if flyctl ssh console --app "$APP_NAME" --command "cd /app && uv run alembic check" &> /dev/null; then
        log_success "Migration scripts are valid"
    else
        log_error "Migration validation failed"
        exit 1
    fi

    # Dry run check
    log_info "Performing dry run migration check..."
    if flyctl ssh console --app "$APP_NAME" --command "cd /app && uv run alembic upgrade --sql head" &> /dev/null; then
        log_success "Dry run migration check passed"
    else
        log_warning "Dry run migration check had issues"
    fi
}

# Run migration
run_migration() {
    local target_revision="${1:-head}"

    log_info "Running migration to: $target_revision"

    # Scale down to prevent conflicts
    log_info "Scaling down application..."
    flyctl scale count 0 --app "$APP_NAME"
    sleep 10

    # Run migration
    log_info "Executing migration..."
    if flyctl ssh console --app "$APP_NAME" --command "cd /app && uv run alembic upgrade $target_revision"; then
        log_success "Migration completed successfully"
    else
        log_error "Migration failed"
        return 1
    fi

    # Scale back up
    log_info "Scaling up application..."
    flyctl scale count 1 --app "$APP_NAME"

    # Wait for app to start
    sleep 30

    # Verify app is healthy
    if curl -sf "https://$APP_NAME.fly.dev/health" > /dev/null; then
        log_success "Application is healthy after migration"
    else
        log_error "Application is not healthy after migration"
        return 1
    fi
}

# Rollback migration
rollback_migration() {
    local target_revision="$1"
    local backup_file="${2:-}"

    log_warning "Rolling back migration to: $target_revision"

    if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
        log_info "Restoring from backup: $backup_file"

        # Scale down
        flyctl scale count 0 --app "$APP_NAME"
        sleep 10

        # Decompress and restore backup
        local restore_file="${backup_file%.gz}"
        gunzip -c "$backup_file" > "$restore_file"

        if flyctl ssh sftp --app "$APP_NAME" put "$restore_file" "$DB_PATH"; then
            log_success "Database restored from backup"
        else
            log_error "Failed to restore from backup"
            return 1
        fi

        # Clean up
        rm -f "$restore_file"

        # Scale up
        flyctl scale count 1 --app "$APP_NAME"
    else
        # Alembic rollback
        log_info "Using Alembic rollback..."

        flyctl scale count 0 --app "$APP_NAME"
        sleep 10

        if flyctl ssh console --app "$APP_NAME" --command "cd /app && uv run alembic downgrade $target_revision"; then
            log_success "Alembic rollback completed"
        else
            log_error "Alembic rollback failed"
            return 1
        fi

        flyctl scale count 1 --app "$APP_NAME"
    fi

    # Verify rollback
    sleep 30
    if curl -sf "https://$APP_NAME.fly.dev/health" > /dev/null; then
        log_success "Application is healthy after rollback"
    else
        log_error "Application is not healthy after rollback"
    fi
}

# Generate new migration
generate_migration() {
    local message="$1"

    log_info "Generating new migration: $message"

    # This should be run locally, not on production
    if command -v uv &> /dev/null; then
        uv run alembic revision --autogenerate -m "$message"
        log_success "Migration generated locally"
        log_info "Review the generated migration before deploying"
    else
        log_error "uv not found. Run this command locally."
        exit 1
    fi
}

# Show migration history
show_history() {
    log_info "Migration history:"
    flyctl ssh console --app "$APP_NAME" --command "cd /app && uv run alembic history --verbose"
}

# Main function
main() {
    local command="${1:-status}"
    local arg1="${2:-}"
    local arg2="${3:-}"

    check_prerequisites

    case "$command" in
        "migrate")
            if ! check_migration_status; then
                local backup_file
                backup_file=$(create_backup)
                validate_migrations

                if run_migration "$arg1"; then
                    log_success "✅ Migration completed successfully!"
                else
                    log_error "❌ Migration failed!"
                    if [ -n "$backup_file" ]; then
                        log_warning "Backup available at: $backup_file"
                        log_info "Use '$0 rollback current $backup_file' to restore"
                    fi
                    exit 1
                fi
            else
                log_info "No migration needed"
            fi
            ;;
        "rollback")
            if [ -z "$arg1" ]; then
                log_error "Please specify target revision: $0 rollback <revision> [backup_file]"
                exit 1
            fi
            rollback_migration "$arg1" "$arg2"
            ;;
        "status")
            check_migration_status
            ;;
        "history")
            show_history
            ;;
        "pending")
            show_pending_migrations
            ;;
        "validate")
            validate_migrations
            ;;
        "generate")
            if [ -z "$arg1" ]; then
                log_error "Please specify migration message: $0 generate '<message>'"
                exit 1
            fi
            generate_migration "$arg1"
            ;;
        "backup")
            create_backup
            ;;
        *)
            echo "Usage: $0 {migrate|rollback|status|history|pending|validate|generate|backup}"
            echo
            echo "Commands:"
            echo "  migrate [revision]       - Run migrations (default: head)"
            echo "  rollback <revision> [backup] - Rollback to revision or restore backup"
            echo "  status                   - Show current migration status"
            echo "  history                  - Show migration history"
            echo "  pending                  - Show pending migrations"
            echo "  validate                 - Validate migration scripts"
            echo "  generate <message>       - Generate new migration (local only)"
            echo "  backup                   - Create database backup"
            echo
            echo "Examples:"
            echo "  $0 status                # Check migration status"
            echo "  $0 migrate               # Run all pending migrations"
            echo "  $0 rollback -1           # Rollback one migration"
            echo "  $0 generate 'Add user table' # Generate new migration"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"