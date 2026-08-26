FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python-is-python3 curl tmux asciinema procps \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir --break-system-packages \
    pytest==8.4.1 pytest-json-ctrf==0.3.5 requests==2.31.0
WORKDIR /app
COPY app/Cargo.toml app/Cargo.lock ./
COPY app/src ./src
COPY app/README.md ./README.md
COPY app/docs ./docs
RUN cargo build --release --locked
