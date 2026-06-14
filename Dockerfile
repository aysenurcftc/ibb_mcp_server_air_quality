FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# First, copy dependency files (for layer caching)
COPY pyproject.toml README.md ./

# Copy uv.lock if it exists, otherwise ignore
COPY uv.lock* ./

# Install dependencies
RUN uv sync --no-dev 2>/dev/null || uv sync --no-dev --no-cache

# Copy source code
COPY src/ ./src/

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  MCP_TRANSPORT=http \
  REDIS_URL=redis://redis:6379/0 \
  CACHE_TTL=60

CMD ["uv", "run", "ibb-mcp"]