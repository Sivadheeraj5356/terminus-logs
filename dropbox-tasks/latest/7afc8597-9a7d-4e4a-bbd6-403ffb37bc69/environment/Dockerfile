FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/0.5.11/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
RUN uv venv /opt/verifier --python 3.13 \
    && uv pip install --python /opt/verifier/bin/python pytest==8.4.1 pytest-json-ctrf==0.3.5

WORKDIR /app

COPY Cargo.toml /app/Cargo.toml
COPY src /app/src
COPY docs /app/docs
COPY data /app/data

CMD ["sleep", "infinity"]
