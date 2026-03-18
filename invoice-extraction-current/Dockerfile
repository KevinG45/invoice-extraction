# =============================================================================
# Invoice Extraction System v2.0.0 - Docker Build
# Multi-stage build: minimal image with GPU support
# =============================================================================

FROM python:3.10-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p outputs/extractions outputs/reports logs models data/input

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Default: run API server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# =============================================================================
# GPU variant (uncomment and build with: docker build -f Dockerfile --target gpu .)
# =============================================================================
# FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 AS gpu
# ... (extend base with CUDA support)
