#!/bin/bash

# Production deployment script for Mochi Donut
# Handles secrets management, pre-deployment checks, and rollback capabilities

set -euo pipefail

# Configuration
APP_NAME="mochi-donut"
HEALTH_CHECK_TIMEOUT=300
ROLLBACK_ON_FAILURE=true

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

# Check if flyctl is installed and authenticated
check_flyctl() {
    log_info "Checking flyctl installation and authentication..."

    if ! command -v flyctl &> /dev/null; then
        log_error "flyctl is not installed. Please install it first."
        exit 1
    fi

    if ! flyctl auth whoami &> /dev/null; then
        log_error "Not authenticated with Fly.io. Run 'flyctl auth login' first."
        exit 1
    fi

    log_success "flyctl is installed and authenticated"
}

# Verify required secrets are set
check_secrets() {
    log_info "Checking required secrets..."

    required_secrets=("SECRET_KEY" "OPENAI_API_KEY" "MOCHI_API_KEY")
    missing_secrets=()

    for secret in "${required_secrets[@]}"; do
        if ! flyctl secrets list --app "$APP_NAME" | grep -q "$secret"; then
            missing_secrets+=("$secret")
        fi
    done

    if [ ${#missing_secrets[@]} -ne 0 ]; then
        log_error "Missing required secrets: ${missing_secrets[*]}"
        log_info "Set secrets using: flyctl secrets set SECRET_NAME=value --app $APP_NAME"
        exit 1
    fi

    log_success "All required secrets are configured"
}

# Run pre-deployment tests
run_tests() {
    log_info "Running pre-deployment tests..."

    if command -v uv &> /dev/null; then
        uv run pytest tests/integration/ -x --tb=short
        log_success "Integration tests passed"
    else
        log_warning "uv not found, skipping tests"
    fi
}

# Deploy application
deploy_app() {
    log_info "Starting deployment to Fly.io..."

    # Get current release for potential rollback
    local current_release
    current_release=$(flyctl releases list --app "$APP_NAME" --json | jq -r '.[0].id' 2>/dev/null || echo "unknown")

    log_info "Current release: $current_release"

    # Deploy with timeout
    if timeout 600 flyctl deploy --remote-only --wait-timeout 600 --app "$APP_NAME"; then
        log_success "Deployment completed successfully"
        return 0
    else
        log_error "Deployment failed or timed out"

        if [ "$ROLLBACK_ON_FAILURE" = true ] && [ "$current_release" != "unknown" ]; then
            log_warning "Initiating automatic rollback to release $current_release"
            flyctl releases rollback "$current_release" --app "$APP_NAME"
            log_info "Rollback completed"
        fi

        return 1
    fi
}

# Health check after deployment
health_check() {
    log_info "Performing post-deployment health checks..."

    local app_url="https://$APP_NAME.fly.dev"
    local start_time=$(date +%s)
    local timeout=$HEALTH_CHECK_TIMEOUT

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -ge $timeout ]; then
            log_error "Health check timed out after ${timeout}s"
            return 1
        fi

        log_info "Checking health endpoint... (attempt $((elapsed / 10 + 1)))"

        if curl -sf "$app_url/health" > /dev/null; then
            log_success "Basic health check passed"
            break
        fi

        sleep 10
    done

    # Detailed health check
    log_info "Running detailed health check..."
    if curl -sf "$app_url/health/detailed" | jq -e '.status == "healthy"' > /dev/null; then
        log_success "Detailed health check passed"
    else
        log_warning "Detailed health check failed, but basic health is OK"
    fi

    # Test API endpoints
    log_info "Testing API endpoints..."
    if curl -sf "$app_url/api/v1/health" > /dev/null; then
        log_success "API endpoints are responding"
    else
        log_warning "API endpoints may not be responding correctly"
    fi
}

# Show deployment information
show_deployment_info() {
    log_success "Deployment completed successfully!"
    echo
    log_info "Application Information:"
    echo "  📍 URL: https://$APP_NAME.fly.dev"
    echo "  📊 Monitoring: https://fly.io/apps/$APP_NAME/monitoring"
    echo "  📜 Logs: flyctl logs --app $APP_NAME"
    echo "  🔄 Releases: flyctl releases list --app $APP_NAME"
    echo
    log_info "Useful Commands:"
    echo "  🚀 Scale machines: flyctl scale count <count> --app $APP_NAME"
    echo "  📈 Monitor: flyctl status --app $APP_NAME"
    echo "  🐛 Debug: flyctl ssh console --app $APP_NAME"
    echo "  ⏪ Rollback: flyctl releases rollback --app $APP_NAME"
}

# Main deployment flow
main() {
    log_info "Starting Mochi Donut production deployment"
    echo "========================================"

    # Pre-deployment checks
    check_flyctl
    check_secrets
    run_tests

    # Deploy
    if deploy_app; then
        health_check
        show_deployment_info
        log_success "✅ Deployment successful!"
        exit 0
    else
        log_error "❌ Deployment failed!"
        exit 1
    fi
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "check")
        check_flyctl
        check_secrets
        log_success "Pre-deployment checks passed"
        ;;
    "test")
        run_tests
        ;;
    "health")
        health_check
        ;;
    "rollback")
        if [ -z "${2:-}" ]; then
            log_error "Please specify release ID: $0 rollback <release-id>"
            exit 1
        fi
        log_info "Rolling back to release $2..."
        flyctl releases rollback "$2" --app "$APP_NAME"
        ;;
    *)
        echo "Usage: $0 {deploy|check|test|health|rollback <release-id>}"
        echo "  deploy  - Full deployment process (default)"
        echo "  check   - Run pre-deployment checks only"
        echo "  test    - Run tests only"
        echo "  health  - Run health checks only"
        echo "  rollback - Rollback to specified release"
        exit 1
        ;;
esac