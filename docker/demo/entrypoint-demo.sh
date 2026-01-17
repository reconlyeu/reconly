#!/bin/bash
# =============================================================================
# Reconly Demo Mode Entrypoint
#
# Simple entrypoint for demo mode:
# 1. Wait for PostgreSQL to be ready
# 2. Start the API server
#
# Database is pre-loaded via init script - no migrations or seeding needed.
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

# =============================================================================
# Wait for PostgreSQL
# =============================================================================
wait_for_postgres() {
    log_info "Waiting for PostgreSQL..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h postgres -U reconly -d reconly > /dev/null 2>&1; then
            log_success "PostgreSQL is ready!"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done

    echo "PostgreSQL did not become ready in time"
    exit 1
}

# =============================================================================
# Main
# =============================================================================
main() {
    echo ""
    echo "=============================================="
    echo "   Reconly Demo Mode"
    echo "=============================================="
    echo ""

    wait_for_postgres

    echo ""
    log_info "Demo mode is ready!"
    log_info "Open http://localhost:${API_PORT:-8002} in your browser"
    echo ""

    # Start the API server
    exec uvicorn reconly_api.main:app --host 0.0.0.0 --port 8000
}

main "$@"
