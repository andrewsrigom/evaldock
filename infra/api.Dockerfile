FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY apps/api apps/api
COPY packages/cli packages/cli
COPY examples examples
COPY fixtures fixtures
COPY alembic.ini ./
RUN uv sync --frozen && useradd --create-home --uid 10001 evaldock && mkdir -p /data/artifacts && chown -R evaldock:evaldock /app /data
USER evaldock
EXPOSE 8080
