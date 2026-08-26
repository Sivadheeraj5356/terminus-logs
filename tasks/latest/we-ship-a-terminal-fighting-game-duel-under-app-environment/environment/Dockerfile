# Canonical Rust runtime: one toolchain, no rustup re-download in a Python stage.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash=5.2.15-2+b13 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/* \
    && tmux -V \
    && asciinema --version

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

ENV PATH="/opt/verifier/bin:${PATH}"

COPY . /app/environment
WORKDIR /app/environment
RUN mkdir -p bin /app/output \
    && cargo build --release \
    && install -m 0755 target/release/duel bin/duel

WORKDIR /app
CMD ["bash"]
