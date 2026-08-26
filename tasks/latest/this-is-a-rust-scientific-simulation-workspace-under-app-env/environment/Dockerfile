FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    patch=2.7.6-7 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/output /app/bin /app/environment/state

RUN python3 -m venv /opt/verifier && \
    /opt/verifier/bin/pip install --no-cache-dir \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5

COPY . /app/environment

ENV PATH="/opt/verifier/bin:/usr/local/cargo/bin:${PATH}"

RUN chmod +x \
      /app/environment/scripts/forge_all.sh \
      /app/environment/scripts/run_k7.sh \
      /app/environment/migrations/purge_k.sh && \
    cd /app/environment && /usr/local/cargo/bin/cargo build --release --locked -p k7 && \
    install -m 0755 target/release/k7 /app/bin/k7

ENV CARGO_NET_OFFLINE=true

WORKDIR /app
