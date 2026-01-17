#!/bin/bash
# =============================================================================
# Reconly Demo Mode Entrypoint
#
# This script:
# 1. Waits for PostgreSQL to be ready
# 2. Waits for Ollama to be ready
# 3. Runs database migrations
# 4. Loads seed data if database is empty (or DEMO_RESET=true)
# 5. Starts the API server
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Parse DATABASE_URL into components
# Format: postgresql://user:password@host:port/database
# =============================================================================
parse_database_url() {
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:]+):.*|\1|')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
    DB_USER=$(echo "$DATABASE_URL" | sed -E 's|.*://([^:]+):.*|\1|')
    DB_PASS=$(echo "$DATABASE_URL" | sed -E 's|.*://[^:]+:([^@]+)@.*|\1|')
    DB_NAME=$(echo "$DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')
}

# =============================================================================
# Wait for PostgreSQL
# =============================================================================
wait_for_postgres() {
    log_info "Waiting for PostgreSQL to be ready..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
            log_success "PostgreSQL is ready!"
            return 0
        fi

        log_info "PostgreSQL not ready yet (attempt $attempt/$max_attempts)..."
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "PostgreSQL did not become ready in time"
    exit 1
}

# =============================================================================
# Wait for Ollama
# =============================================================================
wait_for_ollama() {
    log_info "Waiting for Ollama to be ready..."

    local max_attempts=30
    local attempt=1
    local ollama_url="${OLLAMA_HOST:-http://ollama:11434}"

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "${ollama_url}/api/tags" > /dev/null 2>&1; then
            log_success "Ollama is ready!"
            return 0
        fi

        log_info "Ollama not ready yet (attempt $attempt/$max_attempts)..."
        sleep 2
        attempt=$((attempt + 1))
    done

    log_warn "Ollama did not become ready - continuing anyway (LLM features may not work)"
    return 0
}

# =============================================================================
# Verify Ollama Model
# =============================================================================
verify_ollama_model() {
    local model="${OLLAMA_MODEL:-qwen2.5:3b}"
    local ollama_url="${OLLAMA_HOST:-http://ollama:11434}"

    log_info "Verifying Ollama model '$model' is available..."

    if curl -sf "${ollama_url}/api/tags" | grep -q "$model"; then
        log_success "Model '$model' is available!"
        return 0
    else
        log_warn "Model '$model' not found - it may still be downloading"
        log_info "The ollama-pull service should have handled this"
        return 0
    fi
}

# =============================================================================
# Run Database Migrations
# =============================================================================
run_migrations() {
    log_info "Running database migrations..."

    cd /app/packages/api

    if python -m alembic upgrade head; then
        log_success "Database migrations complete!"
    else
        log_error "Database migrations failed"
        exit 1
    fi

    cd /app
}

# =============================================================================
# Check if Database is Empty
# =============================================================================
is_database_empty() {
    # Check if feeds table has any rows
    # Returns 0 (true) if empty, 1 (false) if has data
    local count
    count=$(PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM feeds;" 2>/dev/null || echo "0")
    count=$(echo "$count" | tr -d ' ')

    [ "$count" = "0" ] || [ -z "$count" ]
}

# =============================================================================
# Load Seed Data
# =============================================================================
load_seed_data() {
    log_info "Loading demo seed data..."

    if python /app/scripts/load_demo_seed.py; then
        log_success "Demo seed data loaded successfully!"
    else
        log_error "Failed to load seed data"
        exit 1
    fi
}

# =============================================================================
# Main
# =============================================================================
main() {
    echo ""
    echo "=============================================="
    echo "   Reconly Demo Mode - Starting Up"
    echo "=============================================="
    echo ""

    # Parse database URL once for all functions
    parse_database_url

    # Step 1: Wait for dependencies
    wait_for_postgres
    wait_for_ollama
    verify_ollama_model

    echo ""

    # Step 2: Run migrations
    run_migrations

    echo ""

    # Step 3: Load seed data if needed
    if [ "${DEMO_RESET:-false}" = "true" ]; then
        log_info "DEMO_RESET=true - forcing seed data reload"
        load_seed_data
    elif is_database_empty; then
        log_info "Database is empty - loading seed data"
        load_seed_data
    else
        log_info "Database already has data - skipping seed load"
        log_info "Set DEMO_RESET=true to force reload seed data"
    fi

    echo ""
    echo "=============================================="
    echo "   Starting Reconly API Server"
    echo "=============================================="
    echo ""
    log_info "Demo mode is enabled"
    log_info "Access the UI at http://localhost:${API_PORT:-8000}"
    echo ""

    # Step 4: Start the API server
    exec uvicorn reconly_api.main:app --host 0.0.0.0 --port 8000
}

# Run main function
main "$@"
