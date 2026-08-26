# Stage 1: builder — compile the workspace using the official Rust image.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS builder

WORKDIR /build

# Copy the full source tree and build in a single pass.
# Layer-caching optimisation: copy manifests first, then source.
COPY Cargo.toml ./
COPY tools/xscope/Cargo.toml ./tools/xscope/Cargo.toml
COPY src/ ./src/
COPY tools/ ./tools/

RUN cargo build --release --workspace 2>&1

# Stage 2: final runtime — sanctioned python:3.11-slim-bookworm base.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

# Install system packages: tmux, asciinema (required by platform),
# plus gcc/libc for cargo link when the agent rebuilds, and curl for rustup.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        curl=7.88.1-10+deb12u14 \
        gcc=4:12.2.0-3 \
        libc6-dev=2.36-9+deb12u14 \
        pkg-config=1.8.1-1 \
        libssl-dev=3.0.20-1~deb12u2 \
        ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Rust toolchain from the builder stage so the agent can rebuild.
COPY --from=builder /usr/local/rustup /usr/local/rustup
COPY --from=builder /usr/local/cargo /usr/local/cargo

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH=/usr/local/cargo/bin:/usr/local/rustup/toolchains/1.85-x86_64-unknown-linux-gnu/bin:${PATH}

# Pre-populate the cargo build cache so offline rebuilds reuse compiled deps.
# The CARGO_TARGET_DIR env var points here so cargo finds pre-built artifacts.
COPY --from=builder /build/target /app/environment/target

# Copy the generated Cargo.lock so offline builds can resolve versions.
COPY --from=builder /build/Cargo.lock /app/environment/Cargo.lock

# Install verifier dependencies into an isolated venv.
# verifier-bake-v2: offline pytest in /opt/verifier
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

ENV PATH=/opt/verifier/bin:${PATH}

# Copy the entire environment tree (source, fixtures, docs, scripts).
COPY . /app/environment/

# Copy the pre-built xscope binary so the agent can run it before rebuilding.
# Use tools/bin/ to avoid collision with the tools/xscope/ package directory.
COPY --chmod=0755 --from=builder /build/target/release/xscope /app/environment/tools/bin/xscope

# Create required output directory.
RUN mkdir -p /app/output

# Make scripts executable.
RUN chmod +x /app/environment/scripts/build_all.sh \
             /app/environment/scripts/drive_suite.sh \
             /app/environment/scripts/clear_scratch.sh \
    && chmod +x /app/environment/tools/bin/xscope

ENV PYTHONPATH=/app
ENV CARGO_TARGET_DIR=/app/environment/target

CMD ["python3", "-c", "print('Legacy record decoder environment ready')"]
