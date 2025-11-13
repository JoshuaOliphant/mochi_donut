#!/bin/bash

# Database backup and restore script for Mochi Donut
# Handles SQLite database backups with rotation and restoration

set -euo pipefail

# Configuration
APP_NAME="mochi-donut"
BACKUP_DIR="./backups"
RETENTION_DAYS=30
DB_PATH="/data/mochi_donut.db"
REMOTE_BACKUP_ENABLED=true

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

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    log_info "Backup directory: $BACKUP_DIR"
}

# Create database backup
backup_database() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/mochi_donut_backup_$timestamp.db"
    local sql_backup="$BACKUP_DIR/mochi_donut_backup_$timestamp.sql"

    log_info "Creating database backup..."

    # Create SQLite database backup
    if flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH .backup $backup_file"; then
        log_success "SQLite backup created: $backup_file"
    else
        log_error "Failed to create SQLite backup"
        return 1
    fi

    # Create SQL dump for portability
    if flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH .dump" > "$sql_backup"; then
        log_success "SQL dump created: $sql_backup"
    else
        log_warning "Failed to create SQL dump"
    fi

    # Compress backups
    gzip "$backup_file" 2>/dev/null || true
    gzip "$sql_backup" 2>/dev/null || true

    log_success "Database backup completed: $timestamp"
    echo "  📁 SQLite backup: ${backup_file}.gz"
    echo "  📄 SQL dump: ${sql_backup}.gz"
}

# List available backups
list_backups() {
    log_info "Available backups:"

    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
        log_warning "No backups found"
        return 0
    fi

    echo
    printf "%-30s %-15s %-10s\n" "BACKUP FILE" "DATE" "SIZE"
    echo "--------------------------------------------------------"

    for backup in "$BACKUP_DIR"/mochi_donut_backup_*.db.gz; do
        if [ -f "$backup" ]; then
            local filename=$(basename "$backup")
            local timestamp=$(echo "$filename" | sed 's/mochi_donut_backup_\(.*\)\.db\.gz/\1/')
            local date_formatted=$(date -d "${timestamp:0:8}" +%Y-%m-%d 2>/dev/null || echo "Unknown")
            local size=$(du -h "$backup" | cut -f1)
            printf "%-30s %-15s %-10s\n" "$filename" "$date_formatted" "$size"
        fi
    done
    echo
}

# Restore database from backup
restore_database() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    log_warning "This will replace the current database. Are you sure? (y/N)"
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_info "Restore cancelled"
        return 0
    fi

    log_info "Restoring database from: $backup_file"

    # Decompress if needed
    local restore_file="$backup_file"
    if [[ "$backup_file" == *.gz ]]; then
        restore_file="${backup_file%.gz}"
        if ! gunzip -c "$backup_file" > "$restore_file"; then
            log_error "Failed to decompress backup file"
            return 1
        fi
    fi

    # Stop application temporarily
    log_info "Scaling down application..."
    flyctl scale count 0 --app "$APP_NAME"

    # Wait for shutdown
    sleep 10

    # Copy backup to production
    if flyctl ssh sftp --app "$APP_NAME" put "$restore_file" "$DB_PATH"; then
        log_success "Database restored successfully"
    else
        log_error "Failed to restore database"
        return 1
    fi

    # Restart application
    log_info "Scaling up application..."
    flyctl scale count 1 --app "$APP_NAME"

    # Clean up temporary files
    if [[ "$backup_file" == *.gz ]]; then
        rm -f "$restore_file"
    fi

    log_success "Database restoration completed"
}

# Clean old backups
clean_old_backups() {
    log_info "Cleaning backups older than $RETENTION_DAYS days..."

    if [ ! -d "$BACKUP_DIR" ]; then
        log_info "No backup directory found"
        return 0
    fi

    local deleted_count=0

    # Find and delete old backups
    while IFS= read -r -d '' backup; do
        rm -f "$backup"
        deleted_count=$((deleted_count + 1))
        log_info "Deleted old backup: $(basename "$backup")"
    done < <(find "$BACKUP_DIR" -name "mochi_donut_backup_*.gz" -mtime +"$RETENTION_DAYS" -print0 2>/dev/null)

    if [ $deleted_count -eq 0 ]; then
        log_info "No old backups to clean"
    else
        log_success "Cleaned $deleted_count old backup(s)"
    fi
}

# Verify database integrity
verify_database() {
    log_info "Verifying database integrity..."

    if flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH 'PRAGMA integrity_check;'" | grep -q "ok"; then
        log_success "Database integrity check passed"
    else
        log_error "Database integrity check failed"
        return 1
    fi

    # Check foreign key constraints
    if flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH 'PRAGMA foreign_key_check;'" | [ $(wc -l) -eq 0 ]; then
        log_success "Foreign key constraints are valid"
    else
        log_warning "Foreign key constraint violations found"
    fi
}

# Export database for migration
export_for_migration() {
    local export_dir="./exports"
    local timestamp=$(date +%Y%m%d_%H%M%S)

    mkdir -p "$export_dir"

    log_info "Exporting database for migration..."

    # Export as SQL
    local sql_export="$export_dir/migration_export_$timestamp.sql"
    if flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH .dump" > "$sql_export"; then
        log_success "SQL export created: $sql_export"
    fi

    # Export as JSON (for API import)
    local json_export="$export_dir/migration_export_$timestamp.json"
    if flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH .mode json .output /tmp/export.json 'SELECT * FROM alembic_version; SELECT * FROM users; SELECT * FROM content; SELECT * FROM prompts;'" && \
       flyctl ssh sftp --app "$APP_NAME" get /tmp/export.json "$json_export"; then
        log_success "JSON export created: $json_export"
    fi

    log_success "Database export completed in: $export_dir"
}

# Show database statistics
show_stats() {
    log_info "Database statistics:"

    echo
    echo "📊 Table Information:"
    flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH \"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;\"" | while read -r table; do
        if [ -n "$table" ]; then
            local count=$(flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH \"SELECT COUNT(*) FROM $table;\"" 2>/dev/null || echo "0")
            printf "  %-20s: %s rows\n" "$table" "$count"
        fi
    done

    echo
    echo "💾 Database Size:"
    flyctl ssh console --app "$APP_NAME" --command "du -h $DB_PATH" | awk '{print "  Database file: " $1}'

    echo
    echo "🔧 Database Info:"
    flyctl ssh console --app "$APP_NAME" --command "sqlite3 $DB_PATH 'PRAGMA user_version; PRAGMA schema_version;'" | (
        read user_version
        read schema_version
        echo "  User version: $user_version"
        echo "  Schema version: $schema_version"
    )
}

# Main function
main() {
    case "${1:-backup}" in
        "backup")
            create_backup_dir
            backup_database
            clean_old_backups
            ;;
        "restore")
            if [ -z "${2:-}" ]; then
                list_backups
                echo
                log_error "Please specify backup file: $0 restore <backup_file>"
                exit 1
            fi
            restore_database "$2"
            ;;
        "list")
            list_backups
            ;;
        "clean")
            clean_old_backups
            ;;
        "verify")
            verify_database
            ;;
        "export")
            export_for_migration
            ;;
        "stats")
            show_stats
            ;;
        *)
            echo "Usage: $0 {backup|restore|list|clean|verify|export|stats}"
            echo "  backup   - Create database backup (default)"
            echo "  restore  - Restore from backup file"
            echo "  list     - List available backups"
            echo "  clean    - Remove old backups"
            echo "  verify   - Check database integrity"
            echo "  export   - Export for migration"
            echo "  stats    - Show database statistics"
            exit 1
            ;;
    esac
}

# Check prerequisites
if ! command -v flyctl &> /dev/null; then
    log_error "flyctl is not installed. Please install it first."
    exit 1
fi

# Run main function
main "$@"