FROM golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS gobuild

WORKDIR /build
COPY s9d /build
RUN go build -o /build/h7d ./cmd/h7d

FROM rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rustbuild

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY mx_core ./mx_core
COPY mx_sim ./mx_sim
RUN cargo fetch --locked \
    && cargo build --release --locked -p mx_sim

FROM rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

COPY --from=gobuild /usr/local/go /usr/local/go

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20230311+deb12u1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

ENV PATH="/opt/verifier/bin:/usr/local/go/bin:/usr/local/cargo/bin:${PATH}"

RUN printf '%s\n' \
    'export PATH="/opt/verifier/bin:/usr/local/go/bin:/usr/local/cargo/bin:${PATH}"' \
    > /etc/profile.d/verifier-path.sh

WORKDIR /app
# verifier-bake-v2: offline pytest in /opt/verifier

COPY Cargo.toml Cargo.lock /app/environment/
COPY mx_core /app/environment/mx_core
COPY mx_sim /app/environment/mx_sim
COPY s9d /app/environment/s9d
COPY fixtures /app/environment/fixtures
COPY docs /app/environment/docs
COPY schemas /app/environment/schemas
COPY scripts /app/environment/scripts

RUN mkdir -p /app/environment/bin /app/output \
    && chmod +x /app/environment/scripts/*.sh \
    && python3 /app/environment/scripts/bake_fixture_seal.py

COPY --from=rustbuild /build/target /app/environment/target
COPY --from=rustbuild /usr/local/cargo/registry /usr/local/cargo/registry
COPY --from=rustbuild /build/target/release/mx_sim /app/environment/bin/h7_sim
COPY --from=gobuild /build/h7d /app/environment/bin/h7d
