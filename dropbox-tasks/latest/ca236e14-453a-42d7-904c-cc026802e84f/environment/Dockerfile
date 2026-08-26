FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

# Install Python and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
    asciinema \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (aiofiles required for FastAPI StaticFiles; pytest for verifier)
RUN pip3 install --break-system-packages \
    fastapi==0.115.5 \
    uvicorn==0.32.1 \
    pydantic==2.10.3 \
    aiofiles==24.1.0 \
    pytest==8.3.3

# Install verifier test dependencies (using lockfile via npm ci for reproducibility)
COPY verifier-package.json /opt/ui-task-tests/package.json
COPY verifier-package-lock.json /opt/ui-task-tests/package-lock.json
RUN cd /opt/ui-task-tests \
    && npm ci \
    && npx playwright install --with-deps chromium

# Pre-install frontend build dependencies (using lockfile via npm ci for reproducibility)
COPY app/frontend/package.json /opt/frontend-deps/package.json
COPY app/frontend/package-lock.json /opt/frontend-deps/package-lock.json
RUN cd /opt/frontend-deps && npm ci

WORKDIR /app
COPY app/ /app/

CMD ["bash"]
