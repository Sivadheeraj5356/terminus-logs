FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app
# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        git \
        python3 python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*
# Install Python dependencies (PIN VERSIONS!)
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && printf '%s\n' '#!/bin/sh' 'exec /opt/venv/bin/python "$@"' > /usr/local/bin/python \
    && chmod +x /usr/local/bin/python
# Copy task files
COPY task_file/ /app/task_file/
# Set up environment
ENV PATH="/opt/venv/bin:/usr/local/cargo/bin:${PATH}" CARGO_TERM_COLOR=never PYTHONPATH=/app
