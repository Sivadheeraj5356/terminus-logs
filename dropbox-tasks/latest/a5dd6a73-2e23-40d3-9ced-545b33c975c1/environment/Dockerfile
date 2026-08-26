FROM rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rustbuilder

WORKDIR /build
COPY pkmerge/Cargo.toml pkmerge/Cargo.toml
COPY pkmerge/Cargo.lock pkmerge/Cargo.lock
COPY pkmerge/src pkmerge/src
RUN cd pkmerge && cargo build --release --locked

FROM golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app/bin \
    && python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest
COPY --from=rustbuilder /build/pkmerge/target/release/pkmerge /app/bin/pkmerge
ENV PATH=/opt/verifier/bin:/usr/local/go/bin:/app/bin:${PATH}
COPY go.mod /app/environment/go.mod
COPY README.md /app/environment/README.md
COPY docs /app/environment/docs
COPY cmd /app/environment/cmd
COPY emit /app/environment/emit
COPY pkg /app/environment/pkg
COPY internal /app/environment/internal
COPY lotledger /app/environment/lotledger
COPY wavebook /app/environment/wavebook
COPY equitygate /app/environment/equitygate
COPY coldlane /app/environment/coldlane
COPY staging /app/environment/staging
COPY scopebook /app/environment/scopebook
COPY support /app/environment/support
COPY pkmerge /app/environment/pkmerge
COPY runtime /app/environment/runtime
COPY requirements.lock /app/environment/requirements.lock
COPY data/immunolab /app/data/immunolab
COPY data/config/immuno.toml /app/config/immuno.toml
COPY data/var/immunoflow_vialremainder.json /app/var/immunoflow_vialremainder.json
COPY data/var/immunoflow_customs.json /app/var/immunoflow_customs.json
WORKDIR /app/environment
RUN /usr/local/go/bin/go build -o /app/bin/immunoflow ./cmd/immunoflow
