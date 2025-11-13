#!/bin/bash

# Validation script for Mochi Donut production deployment
# Comprehensive checks for configuration, dependencies, and deployment readiness

set -euo pipefail

# Configuration
APP_NAME="mochi-donut"
REQUIRED_SECRETS=("SECRET_KEY" "OPENAI_API_KEY" "MOCHI_API_KEY")
OPTIONAL_SECRETS=("JINA_API_KEY" "CHROMA_API_KEY")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((PASSED_CHECKS++))
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
    ((WARNING_CHECKS++))
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED_CHECKS++))
}

check_start() {
    ((TOTAL_CHECKS++))
}

# Check if required tools are installed
check_tools() {
    log_info "Checking required tools..."

    # flyctl
    check_start
    if command -v flyctl &> /dev/null; then
        log_success "flyctl is installed"
    else
        log_error "flyctl is not installed"
    fi

    # docker
    check_start
    if command -v docker &> /dev/null; then
        log_success "docker is installed"
    else
        log_error "docker is not installed"
    fi

    # uv
    check_start
    if command -v uv &> /dev/null; then
        log_success "uv is installed"
    else
        log_warning "uv is not installed (recommended for development)"
    fi

    # curl
    check_start
    if command -v curl &> /dev/null; then
        log_success "curl is available"
    else
        log_error "curl is not available"
    fi

    # jq
    check_start
    if command -v jq &> /dev/null; then
        log_success "jq is available"
    else
        log_warning "jq is not available (recommended for JSON processing)"
    fi
}

# Check Fly.io authentication and app status
check_flyio() {
    log_info "Checking Fly.io configuration..."

    # Authentication
    check_start
    if flyctl auth whoami &> /dev/null; then
        local user=$(flyctl auth whoami 2>/dev/null | head -n1)
        log_success "Authenticated with Fly.io as: $user"
    else
        log_error "Not authenticated with Fly.io"
        return 1
    fi

    # App exists
    check_start
    if flyctl apps list | grep -q "$APP_NAME"; then
        log_success "App '$APP_NAME' exists on Fly.io"
    else
        log_error "App '$APP_NAME' does not exist on Fly.io"
        log_info "Create with: flyctl apps create $APP_NAME"
        return 1
    fi

    # App status
    check_start
    local app_status=$(flyctl status --app "$APP_NAME" --json 2>/dev/null | jq -r '.Status // "unknown"' 2>/dev/null || echo "unknown")
    if [ "$app_status" = "running" ]; then
        log_success "App is running"
    elif [ "$app_status" = "dead" ]; then
        log_warning "App is not running"
    else
        log_warning "App status: $app_status"
    fi
}

# Check secrets configuration
check_secrets() {
    log_info "Checking secrets configuration..."

    # Required secrets
    for secret in "${REQUIRED_SECRETS[@]}"; do
        check_start
        if flyctl secrets list --app "$APP_NAME" 2>/dev/null | grep -q "^$secret"; then
            log_success "Required secret '$secret' is set"
        else
            log_error "Required secret '$secret' is missing"
        fi
    done

    # Optional secrets
    for secret in "${OPTIONAL_SECRETS[@]}"; do
        check_start
        if flyctl secrets list --app "$APP_NAME" 2>/dev/null | grep -q "^$secret"; then
            log_success "Optional secret '$secret' is set"
        else
            log_warning "Optional secret '$secret' is not set"
        fi
    done
}

# Check volumes
check_volumes() {
    log_info "Checking persistent volumes..."

    check_start
    if flyctl volumes list --app "$APP_NAME" 2>/dev/null | grep -q "mochi_donut_data"; then
        local volume_info=$(flyctl volumes list --app "$APP_NAME" --json 2>/dev/null | jq -r '.[] | select(.Name=="mochi_donut_data") | "\(.SizeGb)GB in \(.Region)"' 2>/dev/null || echo "unknown")
        log_success "Persistent volume exists: $volume_info"
    else
        log_error "Persistent volume 'mochi_donut_data' not found"
        log_info "Create with: flyctl volumes create mochi_donut_data --region iad --size 10"
    fi
}

# Check Docker configuration
check_docker() {
    log_info "Checking Docker configuration..."

    # Dockerfile exists
    check_start
    if [ -f "Dockerfile" ]; then
        log_success "Dockerfile exists"
    else
        log_error "Dockerfile not found"
    fi

    # .dockerignore exists
    check_start
    if [ -f ".dockerignore" ]; then
        log_success ".dockerignore exists"
    else
        log_warning ".dockerignore not found (recommended)"
    fi

    # Docker build test
    check_start
    if docker build --quiet --tag mochi-donut:test . &> /dev/null; then
        log_success "Docker image builds successfully"
        docker rmi mochi-donut:test &> /dev/null || true
    else
        log_error "Docker build failed"
    fi
}

# Check fly.toml configuration
check_fly_config() {
    log_info "Checking fly.toml configuration..."

    check_start
    if [ -f "fly.toml" ]; then
        log_success "fly.toml exists"
    else
        log_error "fly.toml not found"
        return 1
    fi

    # Check app name in fly.toml
    check_start
    if grep -q "app = \"$APP_NAME\"" fly.toml; then
        log_success "App name matches in fly.toml"
    else
        log_error "App name mismatch in fly.toml"
    fi

    # Check for persistent volume mount
    check_start
    if grep -q "mochi_donut_data" fly.toml; then
        log_success "Persistent volume configured in fly.toml"
    else
        log_error "Persistent volume not configured in fly.toml"
    fi

    # Check for health checks
    check_start
    if grep -q "path = \"/health\"" fly.toml; then
        log_success "Health checks configured"
    else
        log_warning "Health checks not configured"
    fi
}

# Check dependencies
check_dependencies() {
    log_info "Checking Python dependencies..."

    # pyproject.toml
    check_start
    if [ -f "pyproject.toml" ]; then
        log_success "pyproject.toml exists"
    else
        log_error "pyproject.toml not found"
    fi

    # uv.lock
    check_start
    if [ -f "uv.lock" ]; then
        log_success "uv.lock exists"
    else
        log_warning "uv.lock not found (run 'uv lock')"
    fi

    # Check if dependencies can be installed
    if command -v uv &> /dev/null; then
        check_start
        if uv sync --check &> /dev/null; then
            log_success "Dependencies are up to date"
        else
            log_warning "Dependencies may need updating (run 'uv sync')"
        fi
    fi
}

# Check database configuration
check_database() {
    log_info "Checking database configuration..."

    # Alembic configuration
    check_start
    if [ -f "alembic.ini" ]; then
        log_success "alembic.ini exists"
    else
        log_error "alembic.ini not found"
    fi

    # Alembic directory
    check_start
    if [ -d "alembic" ]; then
        log_success "alembic directory exists"
    else
        log_error "alembic directory not found"
    fi

    # Migration scripts
    check_start
    if [ -d "alembic/versions" ] && [ "$(ls -A alembic/versions)" ]; then
        local migration_count=$(ls alembic/versions/*.py 2>/dev/null | wc -l)
        log_success "$migration_count migration scripts found"
    else
        log_warning "No migration scripts found"
    fi
}

# Check CI/CD configuration
check_cicd() {
    log_info "Checking CI/CD configuration..."

    # GitHub Actions
    check_start
    if [ -f ".github/workflows/deploy.yml" ]; then
        log_success "GitHub Actions deployment workflow exists"
    else
        log_warning "GitHub Actions deployment workflow not found"
    fi

    check_start
    if [ -f ".github/workflows/test.yml" ]; then
        log_success "GitHub Actions test workflow exists"
    else
        log_warning "GitHub Actions test workflow not found"
    fi

    # Production scripts
    check_start
    if [ -f "scripts/production/deploy.sh" ] && [ -x "scripts/production/deploy.sh" ]; then
        log_success "Production deployment script exists and is executable"
    else
        log_warning "Production deployment script not found or not executable"
    fi
}

# Check application health (if deployed)
check_app_health() {
    log_info "Checking application health..."

    local app_url="https://$APP_NAME.fly.dev"

    # Basic health check
    check_start
    if curl -sf "$app_url/health" > /dev/null 2>&1; then
        log_success "Application health endpoint responds"
    else
        log_warning "Application health endpoint not accessible (app may not be deployed)"
        return 0
    fi

    # Detailed health check
    check_start
    local health_status=$(curl -sf "$app_url/health/detailed" 2>/dev/null | jq -r '.status' 2>/dev/null || echo "unknown")
    if [ "$health_status" = "healthy" ]; then
        log_success "Application detailed health check passes"
    else
        log_warning "Application detailed health check: $health_status"
    fi

    # API endpoints
    check_start
    if curl -sf "$app_url/api/v1/health" > /dev/null 2>&1; then
        log_success "API endpoints are accessible"
    else
        log_warning "API endpoints may not be accessible"
    fi
}

# Check environment files
check_environment() {
    log_info "Checking environment configuration..."

    # Development environment
    check_start
    if [ -f ".env.sample" ]; then
        log_success ".env.sample exists"
    else
        log_warning ".env.sample not found"
    fi

    # Production environment template
    check_start
    if [ -f "env.production.sample" ]; then
        log_success "env.production.sample exists"
    else
        log_warning "env.production.sample not found"
    fi

    # Check for .env files in git
    check_start
    if git ls-files | grep -q "\.env$"; then
        log_error ".env file is tracked in git (security risk)"
    else
        log_success "No .env files tracked in git"
    fi
}

# Check security configuration
check_security() {
    log_info "Checking security configuration..."

    # HTTPS enforcement
    check_start
    if grep -q "force_https = true" fly.toml; then
        log_success "HTTPS enforcement enabled"
    else
        log_warning "HTTPS enforcement not configured"
    fi

    # Rate limiting
    check_start
    if grep -q "RATE_LIMIT_ENABLED" env.production.sample; then
        log_success "Rate limiting configuration found"
    else
        log_warning "Rate limiting not configured"
    fi

    # CORS configuration
    check_start
    if grep -q "CORS_ORIGINS" env.production.sample; then
        log_success "CORS configuration found"
    else
        log_warning "CORS not configured"
    fi
}

# Generate report
generate_report() {
    echo
    echo "============================================"
    echo "           VALIDATION REPORT"
    echo "============================================"
    echo
    echo "Total Checks: $TOTAL_CHECKS"
    echo -e "Passed: ${GREEN}$PASSED_CHECKS${NC}"
    echo -e "Warnings: ${YELLOW}$WARNING_CHECKS${NC}"
    echo -e "Failed: ${RED}$FAILED_CHECKS${NC}"
    echo

    if [ $FAILED_CHECKS -eq 0 ]; then
        if [ $WARNING_CHECKS -eq 0 ]; then
            echo -e "${GREEN}🎉 All checks passed! Ready for production deployment.${NC}"
            exit 0
        else
            echo -e "${YELLOW}⚠️  All critical checks passed, but there are warnings to review.${NC}"
            exit 0
        fi
    else
        echo -e "${RED}❌ Some checks failed. Please fix the issues before deploying.${NC}"
        exit 1
    fi
}

# Main validation function
main() {
    echo "============================================"
    echo "      MOCHI DONUT DEPLOYMENT VALIDATION"
    echo "============================================"
    echo

    check_tools
    echo
    check_flyio
    echo
    check_secrets
    echo
    check_volumes
    echo
    check_docker
    echo
    check_fly_config
    echo
    check_dependencies
    echo
    check_database
    echo
    check_cicd
    echo
    check_environment
    echo
    check_security
    echo
    check_app_health
    echo

    generate_report
}

# Handle script arguments
case "${1:-validate}" in
    "validate")
        main
        ;;
    "tools")
        check_tools
        generate_report
        ;;
    "flyio")
        check_flyio
        check_secrets
        check_volumes
        generate_report
        ;;
    "docker")
        check_docker
        generate_report
        ;;
    "health")
        check_app_health
        generate_report
        ;;
    *)
        echo "Usage: $0 {validate|tools|flyio|docker|health}"
        echo "  validate - Run all validation checks (default)"
        echo "  tools    - Check required tools only"
        echo "  flyio    - Check Fly.io configuration only"
        echo "  docker   - Check Docker configuration only"
        echo "  health   - Check application health only"
        exit 1
        ;;
esac