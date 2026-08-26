FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36
RUN apt-get update && apt-get install -y --no-install-recommends asciinema=2.2.0-1 ca-certificates=20230311+deb12u1 python3=3.11.2-1+b1 python3-venv=3.11.2-1+b1 tmux=3.3a-3 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/verifier/requirements.txt
COPY wheels/ /tmp/verifier/wheels/
RUN python3 -m venv /opt/verifier
RUN /opt/verifier/bin/pip install --no-cache-dir --no-index --find-links=/tmp/verifier/wheels --only-binary=:all: --require-hashes --no-deps -r /tmp/verifier/requirements.txt
RUN rm -rf /tmp/verifier
ENV PATH=/opt/verifier/bin:${PATH} CARGO_NET_OFFLINE=true
WORKDIR /app
COPY Cargo.toml Cargo.lock CUBIC_DIFFRACTION_PROTOCOL.md ./
COPY src/ ./src/
COPY examples/ ./examples/
RUN cargo test --offline --locked && cargo build --offline --locked --release && mkdir -p /app/bin /logs/verifier /logs/agent && cp target/release/cubic-index /app/bin/cubic-index && rm -rf target
CMD ["sleep", "infinity"]
