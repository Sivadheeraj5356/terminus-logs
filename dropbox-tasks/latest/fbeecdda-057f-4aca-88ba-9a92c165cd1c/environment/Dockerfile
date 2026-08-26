# Rust builder
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-builder
WORKDIR /build
COPY Cargo.toml Cargo.toml
COPY src src
RUN cargo build --release --offline

# Go builder
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-builder
WORKDIR /build
COPY go.mod go.mod
COPY spliceclock spliceclock
COPY matchmesh matchmesh
COPY vaultseal vaultseal
COPY cmd/cinecont cmd/cinecont
RUN go build -o /build/cinecont ./cmd/cinecont

# Final runtime
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    build-essential=12.9 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
ENV PATH=/opt/verifier/bin:/usr/local/go/bin:/usr/local/cargo/bin:${PATH}

COPY --from=public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac /usr/local/go /usr/local/go
COPY --from=public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 /usr/local/cargo /usr/local/cargo
COPY --from=public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 /usr/local/rustup /usr/local/rustup
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo

RUN mkdir -p /app/bin /app/output
COPY --from=rust-builder /build/target/release/denscore /app/bin/denscore
COPY --from=go-builder /build/cinecont /app/bin/cinecont
COPY . /app/environment

ENV DENSCORE_BIN=/app/bin/denscore
CMD ["python3", "-c", "print('Environment ready')"]
