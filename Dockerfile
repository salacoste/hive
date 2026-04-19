# syntax=docker/dockerfile:1.7

# ── Stage 1: Build frontend ────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY core/frontend/package.json core/frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY core/frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime + CLI + API server ────
FROM python:3.11-slim

WORKDIR /app

ARG HIVE_DOCKER_INSTALL_NODE=0
ARG HIVE_DOCKER_INSTALL_GO=0
ARG HIVE_DOCKER_INSTALL_RUST=0
ARG HIVE_DOCKER_INSTALL_JAVA=0

# Container-native ops baseline (upstream/preflight tooling).
RUN set -eux; \
    apt-get update; \
    base_packages="git jq curl ca-certificates"; \
    extra_packages=""; \
    if [ "${HIVE_DOCKER_INSTALL_NODE}" = "1" ]; then \
      extra_packages="${extra_packages} nodejs npm"; \
    fi; \
    if [ "${HIVE_DOCKER_INSTALL_GO}" = "1" ]; then \
      extra_packages="${extra_packages} golang"; \
    fi; \
    if [ "${HIVE_DOCKER_INSTALL_RUST}" = "1" ]; then \
      extra_packages="${extra_packages} rustc cargo"; \
    fi; \
    if [ "${HIVE_DOCKER_INSTALL_JAVA}" = "1" ]; then \
      extra_packages="${extra_packages} default-jdk-headless"; \
    fi; \
    apt-get install -y --no-install-recommends ${base_packages} ${extra_packages}; \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy workspace manifests + lock first so dependency layer is cacheable across source edits.
COPY pyproject.toml uv.lock ./
COPY .python-version ./
COPY core/pyproject.toml core/README.md core/
COPY tools/pyproject.toml tools/README.md tools/

# Phase 1: install all locked dependencies except editable workspace packages.
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-workspace

# Install Chromium runtime for Playwright-based web_scrape MCP tool.
# Keep this step before source copy so browser downloads stay cached across code-only edits.
ARG HIVE_DOCKER_INSTALL_PLAYWRIGHT=1
RUN if [ "${HIVE_DOCKER_INSTALL_PLAYWRIGHT}" = "1" ]; then \
      uv run playwright install --with-deps chromium; \
      chmod -R a+rX "${PLAYWRIGHT_BROWSERS_PATH}"; \
    else \
      echo "Skipping Playwright install in Docker image (HIVE_DOCKER_INSTALL_PLAYWRIGHT=${HIVE_DOCKER_INSTALL_PLAYWRIGHT})"; \
    fi

# Copy runtime sources and install workspace packages in editable mode.
COPY core/framework/ core/framework/
COPY tools/src/ tools/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --reinstall-package framework --reinstall-package tools

# Copy MCP server files
COPY tools/mcp_server.py tools/
COPY tools/coder_tools_server.py tools/
COPY tools/files_server.py tools/
COPY tools/mcp_servers.json tools/
COPY scripts/ scripts/
COPY docs/ docs/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist /app/core/frontend/dist

# Copy CLI entry point
COPY hive ./

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create non-root user and directories
RUN useradd -m -u 1001 hiveuser \
    && mkdir -p /data/storage /data/credentials /app/exports /app/examples /home/hiveuser/.hive \
    && chown -R hiveuser:hiveuser /data /app/exports /app/examples /home/hiveuser /app/docs

USER hiveuser

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8787/api/health', timeout=5).read()" || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["serve"]
