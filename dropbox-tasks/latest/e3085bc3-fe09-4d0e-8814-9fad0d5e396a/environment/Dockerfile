# Builder stages use the digest-pinned public Rust and Go images. No single
# ghcr.io/laude-institute/t-bench image currently ships both toolchains; the
# runtime stage uses the canonical debian:bookworm-slim with both toolchains
# layered in so the lab can be rebuilt offline in-container.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-build
WORKDIR /build
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
COPY hook/Cargo.toml hook/Cargo.lock ./
COPY hook/src ./src
RUN cargo build --release --locked

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS go-build
WORKDIR /build
COPY go.mod ./
RUN GOFLAGS=-mod=mod go mod download
COPY cmd ./cmd
COPY internal ./internal
COPY tools ./tools
RUN GOFLAGS=-mod=mod go build -trimpath -buildvcs=false -o /out/loader ./cmd/loader
RUN GOFLAGS=-mod=mod go build -trimpath -buildvcs=false -o /out/reconcile ./cmd/reconcile
RUN GOFLAGS=-mod=mod go build -trimpath -buildvcs=false -o /out/dump ./tools/dump

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d
# asciinema refuses to start without a UTF-8 locale; bookworm-slim sets none, so
# the agent harness (tmux launched under asciinema) would crash on startup.
# C.UTF-8 is provided by glibc without locale-gen and satisfies the UTF-8 check.
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
    && rm -rf /var/lib/apt/lists/*
RUN command -v tmux && command -v asciinema && tmux -V && asciinema --version \
    && python3 -c "import locale; locale.setlocale(locale.LC_ALL, ''); cs = locale.nl_langinfo(locale.CODESET); print('codeset', cs); assert cs.lower() in ('utf-8', 'utf8'), cs"
COPY verifier-requirements.txt /tmp/verifier-requirements.txt
# Verifier deps: pytest==8.4.1 pytest-json-ctrf==0.3.5
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/verifier-requirements.txt
RUN ln -sf "$(command -v python3)" /usr/local/bin/python && rm -f /tmp/verifier-requirements.txt
COPY --from=rust-build /usr/local/cargo /usr/local/cargo
COPY --from=rust-build /usr/local/rustup /usr/local/rustup
COPY --from=go-build /usr/local/go /usr/local/go
ENV PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH}"
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && go version && cargo --version
ENV GOPROXY=off
ENV GOFLAGS=-mod=mod
COPY go.mod /app/
COPY cmd /app/cmd
COPY internal /app/internal
COPY tools /app/tools
COPY hook /app/hook
COPY data /app/data
COPY docs /app/docs
COPY schemas /app/schemas
COPY scripts /app/scripts
COPY README.md /app/README.md
COPY --from=go-build /out/loader /app/bin/loader
COPY --from=go-build /out/reconcile /app/bin/reconcile
COPY --from=go-build /out/dump /app/bin/dump
COPY --from=rust-build /build/target/release/hook /app/hook/target/release/hook
LABEL org.opencontainers.image.title="ima-measure-appraisal-order" \
      org.opencontainers.image.description="Offline integrity measurement and appraisal enforcement lab with Go policy lowering and Rust replay worker." \
      org.opencontainers.image.source="https://github.com/nordlane-labs/imlab-offline" \
      org.opencontainers.image.revision="1.0.0" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.created="2026-07-10T00:00:00Z" \
      org.opencontainers.image.licenses="Apache-2.0"
WORKDIR /app
