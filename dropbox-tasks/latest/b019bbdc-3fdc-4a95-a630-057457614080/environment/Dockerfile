FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust_builder
WORKDIR /build
COPY oxk/Cargo.toml oxk/Cargo.lock oxk/
COPY oxk/src oxk/src
WORKDIR /build/oxk
RUN cargo build --release --locked

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
ENV DEBIAN_FRONTEND=noninteractive TERM=xterm LANG=C.UTF-8 LC_ALL=C.UTF-8 TMUX_TMPDIR=/var/tmp/tmux
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 build-essential=12.9 ca-certificates=20230311+deb12u1 \
    python3=3.11.2-1+b1 python3-pip=23.0.1+dfsg-1 python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux /app/bin /app/output /app/var/splicekit /app/data/scenarios \
    && chmod 1777 /var/tmp/tmux && chmod 777 /app/bin /app/output /app/var/splicekit \
    && rm -rf /var/lib/apt/lists/*
COPY runtime/tmux.conf /etc/tmux.conf
RUN python3 -m venv /opt/verifier
RUN /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest
ENV PATH=/opt/verifier/bin:/usr/local/cargo/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
COPY --from=rust_builder /usr/local/rustup /usr/local/rustup
COPY --from=rust_builder /usr/local/cargo /usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo
COPY --from=rust_builder /build/oxk/target/release/oxk-cli /app/bin/oxk-cli
COPY --from=rust_builder /build/oxk/target /app/environment/oxk/target
COPY go.mod /app/environment/go.mod
COPY cmd /app/environment/cmd
COPY internal /app/environment/internal
COPY pkg /app/environment/pkg
COPY oxk /app/environment/oxk
COPY data /app/data
COPY docs /app/environment/docs
COPY README.md /app/environment/README.md
RUN cd /app/environment && go build -o /app/bin/splicectl ./cmd/splicectl && rm -rf /root/.cache/go-build \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo
RUN mkdir -p /opt/splicekit && cp -a /app/data/scenarios /opt/splicekit/scenarios-pristine
