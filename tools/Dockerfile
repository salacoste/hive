# Aden Tools MCP Server
# Builds from root workspace context so uv resolves framework dependency

FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace definitions
COPY pyproject.toml ./

# Copy source code
COPY src ./src

# Copy MCP server entry point
COPY mcp_server.py .

# Install via uv (resolves workspace dependency on framework)
RUN uv pip install --no-cache-dir -e .

# Install Google Chrome (stable) for GCU browser tools via CDP
RUN apt-get update && apt-get install -y wget gnupg \
    && mkdir -p /etc/apt/keyrings \
    && wget -q -O /etc/apt/keyrings/google-chrome.asc https://dl.google.com/linux/linux_signing_key.pub \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.asc] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1001 appuser \
    && mkdir -p /app/workdir/workspaces \
    && chown -R appuser:appuser /app

USER appuser

# Workspace persistence
VOLUME ["/app/workspaces"]

EXPOSE 4001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:4001/health').raise_for_status()" || exit 1

CMD ["python", "mcp_server.py"]
