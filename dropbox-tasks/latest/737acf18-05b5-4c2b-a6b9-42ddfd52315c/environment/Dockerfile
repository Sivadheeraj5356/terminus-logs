FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    patch=2.7.6-7 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5
ENV PATH=/opt/verifier/bin:${PATH}
ENV CARGO_HOME=/usr/local/cargo

COPY cargo-config.toml Cargo.toml Cargo.lock /app/
COPY src/ /app/src/
COPY mirror/ /app/mirror/
COPY data/ /app/data/
COPY docs/ /app/docs/
COPY scripts/ /app/scripts/

RUN mkdir -p /app/.cargo /app/output \
    && cp /app/cargo-config.toml /app/.cargo/config.toml \
    && chmod +x /app/scripts/*.sh \
    && rm -rf /usr/local/cargo/registry /usr/local/cargo/git

CMD ["bash", "-lc", "echo environment ready"]
