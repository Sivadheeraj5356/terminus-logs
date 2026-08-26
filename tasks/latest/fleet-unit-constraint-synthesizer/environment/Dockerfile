FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust_builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends pkg-config=1.8.1-1 && rm -rf /var/lib/apt/lists/*
COPY fe-core/Cargo.toml fe-core/Cargo.lock ./
COPY fe-core/src ./src
RUN cargo build --release --locked

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go_builder
WORKDIR /build
COPY go/go.mod ./
COPY go/pkg ./pkg
COPY go/cmd ./cmd
RUN go mod tidy && go build -o /out/fleet_emit ./cmd/fleet_emit && go build -o /out/trace_emit ./cmd/trace_emit

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    build-essential=12.9 \
    ca-certificates=20230311+deb12u1 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    systemd=252.39-1~deb12u2 \
    tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/bin /app/output
COPY --from=rust_builder /usr/local/cargo /usr/local/cargo
COPY --from=rust_builder /usr/local/rustup /usr/local/rustup
COPY --from=go_builder /usr/local/go /usr/local/go
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
RUN /usr/local/cargo/bin/rustup default 1.85.1-x86_64-unknown-linux-gnu
RUN python3 -m venv /opt/verifier && \
    /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
COPY --from=rust_builder /build/target /app/environment/fe-core/target
COPY --from=rust_builder /build/target/release/fe_run /app/bin/fe_run
COPY --from=go_builder /out/fleet_emit /app/bin/fleet_emit
COPY --from=go_builder /out/trace_emit /app/bin/trace_emit
COPY . /app/environment
RUN chmod +x /app/environment/scripts/*.sh /app/environment/scripts/pack_tar.py
ENV PATH=/opt/verifier/bin:/usr/local/cargo/bin:/usr/local/go/bin:/app/bin:${PATH}
ENV GOPROXY=off
ENV GOSUMDB=off
