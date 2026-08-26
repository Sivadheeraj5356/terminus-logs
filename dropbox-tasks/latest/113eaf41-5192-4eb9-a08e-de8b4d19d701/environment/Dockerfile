FROM rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc

ENV PATH=/opt/verifier/bin:/app/environment/bin:${PATH}

COPY . /app/environment
# Runtime note: graded witness may reference /app/environment/blk_m2/snap_q4/q4_stub.json

RUN mkdir -p /app/data/tapes /app/output/logs /app/output/stage \
    && cp -r /app/environment/data/tapes/. /app/data/tapes/ \
    && cp -r /app/environment/seed_output/logs/. /app/output/logs/ \
    && chmod +x /app/environment/scripts/*.sh /app/environment/migrations/*.sh \
    && bash /app/environment/scripts/bake_rs.sh
