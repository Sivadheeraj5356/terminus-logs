FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        curl \
        gcc \
        libc6-dev \
        less \
        nano \
        procps \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Verifier dependencies are baked into a dedicated venv so tests/test.sh can use the
# canonical Harbor entrypoint without installing anything at verifier runtime.
RUN python -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.2 \
        pytest-json-ctrf==0.5.0

ENV RUSTUP_VERSION=1.27.1 \
    RUST_VERSION=1.87.0
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
        amd64) rustArch='x86_64-unknown-linux-gnu'; rustupSha256='6aeece6993e902708983b209d04c0d1dbb14ebb405ddb87def578d41f920f56d' ;; \
        arm64) rustArch='aarch64-unknown-linux-gnu'; rustupSha256='1cffbf51e63e634c746f741de50649bbbcbd9dbe1de363c9ecef64e278dba2b2' ;; \
        *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    url="https://static.rust-lang.org/rustup/archive/${RUSTUP_VERSION}/${rustArch}/rustup-init"; \
    curl -fsSL "$url" -o /tmp/rustup-init; \
    echo "${rustupSha256}  /tmp/rustup-init" | sha256sum -c -; \
    chmod +x /tmp/rustup-init; \
    /tmp/rustup-init -y --no-modify-path --profile minimal --default-toolchain "${RUST_VERSION}"; \
    rm -f /tmp/rustup-init
ENV PATH="/root/.cargo/bin:${PATH}"

COPY task_file/input /app/task_file/input
COPY task_file/src /app/task_file/src
RUN rm -rf /app/task_file/output && mkdir -p /app/task_file/output
