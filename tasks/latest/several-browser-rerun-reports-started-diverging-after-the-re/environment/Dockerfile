FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        python3 \
        python3-pip \
        python3-venv \
        sqlite3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Create Python virtual environment for test runners
# Pre-install pytest and pytest-json-ctrf so tests can run offline
# IMPORTANT: Versions must match steps/milestone_*/tests/test.sh
RUN python3 -m venv /opt/test-venv \
    && /opt/test-venv/bin/pip install --no-cache-dir \
        pytest==9.0.3 \
        pytest-json-ctrf==0.5.0

ENV PATH="/opt/test-venv/bin:${PATH}"

WORKDIR /app

COPY app/package.json app/package-lock.json ./

RUN npm ci --omit=dev

COPY app/ .

COPY verifier-reference/ /opt/verifier-reference/

RUN node /app/scripts/seed_db.js

CMD ["bash"]
