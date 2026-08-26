FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS builder
WORKDIR /app/environment
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip python3-venv tmux asciinema && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --break-system-packages pytest==8.3.2 pytest-timeout==2.3.1 pytest-json-ctrf==0.5.0
COPY Cargo.toml Cargo.lock ./
COPY match_parser/ match_parser/
COPY rating_engine/ rating_engine/
COPY kfactor_calculator/ kfactor_calculator/
COPY leaderboard/ leaderboard/
COPY tools/ tools/
COPY traces/ traces/
COPY docs/ docs/
COPY scripts/ scripts/
RUN cargo fetch --locked
RUN cargo build --workspace --release --locked
RUN cp target/release/elo_verify /app/environment/elo_verify
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip python3-venv tmux asciinema && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --break-system-packages pytest==8.3.2 pytest-timeout==2.3.1 pytest-json-ctrf==0.5.0
COPY --from=builder /app/environment /app/environment
COPY --from=builder /usr/local/cargo/registry /usr/local/cargo/registry
RUN ln -sf /app/environment/docs /app/docs
WORKDIR /app
CMD ["/bin/bash"]
