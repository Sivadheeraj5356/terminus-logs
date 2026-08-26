# Justification: Using canonical Rust base image as specified in prompt.md for compiled tasks
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

# Install system tools required by agent runtime and tests
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    python3 \
    python3-pip \
    bash \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --require-hashes --no-deps -r /tmp/requirements.txt --break-system-packages

# Ensure cargo is always on PATH (required for interactive tmux/asciinema sessions)
ENV PATH="/usr/local/cargo/bin:${PATH}"

WORKDIR /app

# Copy manifests first for cache-friendly dep fetching
COPY Cargo.toml Cargo.lock /app/
RUN mkdir src && echo "fn main(){}" > src/main.rs && cargo build --release --locked && rm -rf src

# Copy source and rebuild
COPY src/ /app/src/
RUN touch src/main.rs && cargo build --release --locked

# Copy remaining files
COPY config/ /app/config/
COPY docs/ /app/docs/
COPY input/ /app/input/
COPY scripts/ /app/scripts/
COPY utils/ /app/utils/

RUN chmod +x /app/scripts/validate_output.sh

# Create output directory
RUN mkdir -p /app/output

RUN echo 'export PATH="/usr/local/cargo/bin:$PATH"' >> /root/.bashrc
