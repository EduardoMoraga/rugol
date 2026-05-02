FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Node.js 20 (needed for the `claude` CLI bundled in the runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY core/requirements.txt /app/core/requirements.txt
RUN pip install -r /app/core/requirements.txt

# Create non-root user
RUN useradd -u 1000 -m -s /bin/bash appuser

# Copy source
COPY core /app/core

# Workspace bind-mounted at runtime
RUN mkdir -p /app/agents /app/skills /app/data /app/logs && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
