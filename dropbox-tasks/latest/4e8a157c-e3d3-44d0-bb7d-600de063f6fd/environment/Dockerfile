FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    curl=7.88.1-10+deb12u15 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-randomly==3.16.0
ENV PATH=/opt/verifier/bin:/usr/local/cargo/bin:${PATH}
ENV CARGO_HOME=/opt/cargo-home
ENV CARGO_TARGET_DIR=/app/environment/target

RUN mkdir -p /app/environment /app/output /app/bin /logs/verifier /opt/cargo-home

COPY . /app/environment

RUN chmod +x /app/environment/k4m/build_wrap.sh \
    && cd /app/environment \
    && cargo generate-lockfile \
    && cargo build --release -p drv \
    && cp -f target/release/cg_xmit /app/bin/cg_xmit \
    && chmod +x /app/bin/cg_xmit \
    && cargo build --offline --release -p drv

WORKDIR /app

CMD ["python3", "-c", "print('Environment ready')"]
