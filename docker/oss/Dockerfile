# =============================================================================
# Stage 1: Build UI
# =============================================================================
FROM node:20-alpine AS ui-builder

WORKDIR /app/ui

# Copy UI package files
COPY ui/package*.json ./

# Install dependencies
RUN npm ci

# Copy UI source
COPY ui/ ./

# Build the UI (static site generation)
RUN npm run build

# =============================================================================
# Stage 2: Python API with UI
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages
COPY packages/core /app/packages/core
COPY packages/api /app/packages/api

# Install Python dependencies
RUN pip install --no-cache-dir \
    /app/packages/core \
    /app/packages/api

# Copy built UI from builder stage
COPY --from=ui-builder /app/ui/dist /app/ui/dist

# Copy seed script and data
COPY scripts/load_demo_seed.py /app/scripts/
COPY docker/demo/seed /app/seed

# Copy entrypoint script
COPY docker/oss/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
