# Multi-stage Docker build for Mochi Donut FastAPI application
# Optimized for Python 3.12 with uv package manager

# Build stage - Install dependencies and build application
FROM python:3.12-slim as builder

# Install system dependencies required for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv

# Set work directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv (creates .venv in /app)
RUN uv sync --frozen --no-dev

# Copy source code
COPY . .

# Create wheel for faster installation in production stage
RUN uv build

# Production stage - Minimal runtime image
FROM python:3.12-slim as production

# Install system dependencies required for runtime
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv in production stage
RUN pip install uv

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy built wheel and dependency files from builder
COPY --from=builder /app/dist/*.whl ./
COPY --from=builder /app/pyproject.toml /app/uv.lock ./

# Install the application and dependencies
RUN uv pip install --system --no-cache-dir *.whl

# Copy application source code
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Expose port
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Default command - can be overridden for different services
CMD ["sh", "-c", "uv run uvicorn src.app.main:app --host 0.0.0.0 --port $PORT --workers 1"]