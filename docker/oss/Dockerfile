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

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Default command: run the API server
CMD ["uvicorn", "reconly_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
