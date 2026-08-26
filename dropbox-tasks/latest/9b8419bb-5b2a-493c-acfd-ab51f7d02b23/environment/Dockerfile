# Builder: canonical Terminal-Bench Rust base (docs/PLATFORM_AUTO_EVAL.md).
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rustbuilder

WORKDIR /build
COPY z4/Cargo.toml z4/Cargo.toml
COPY z4/Cargo.lock z4/Cargo.lock
COPY z4/src z4/src
RUN cd z4 && cargo build --release --locked

# Final runtime: canonical Terminal-Bench Go base (docs/PLATFORM_AUTO_EVAL.md).
# Rust toolchain is copied from the builder stage so agents and the verifier can
# rebuild /app/bin/boardctl and /app/bin/ixcore after source edits.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_NET_OFFLINE=true
ENV PATH="/opt/verifier-venv/bin:/app/bin:/usr/local/go/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        patch=2.7.6-7 \
        python3=3.11.2-1+b1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
        util-linux=2.38.1-5+deb12u3 \
    && groupadd --system boardagent \
    && useradd --system --gid boardagent --home-dir /var/lib/boardagent --shell /usr/sbin/nologin boardagent \
    && mkdir -p /app/bin /app/output /app/var /logs/verifier /var/tmp/tmux \
        /var/lib/verifier/build-work /var/lib/verifier/bin /var/lib/boardagent \
    && chmod 1777 /var/tmp/tmux \
    && chmod 700 /logs/verifier \
    && chown root:root /var/lib/verifier/build-work /var/lib/verifier/bin \
    && chmod 700 /var/lib/verifier/build-work \
    && chmod 755 /var/lib/verifier/bin \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

COPY runtime/tmux.conf /etc/tmux.conf
COPY . /app/environment/
COPY --from=rustbuilder /build/z4/target/release/ixcore /app/bin/ixcore
COPY --from=rustbuilder /usr/local/cargo /usr/local/cargo
COPY --from=rustbuilder /usr/local/rustup /usr/local/rustup

# Keep go/cargo/rustc discoverable even when login shells reset PATH.
RUN ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustdoc /usr/local/bin/rustdoc \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && printf '%s\n' \
      'export CARGO_HOME=/usr/local/cargo' \
      'export RUSTUP_HOME=/usr/local/rustup' \
      'export CARGO_NET_OFFLINE=true' \
      'export PATH="/opt/verifier-venv/bin:/app/bin:/usr/local/go/bin:/usr/local/cargo/bin:${PATH}"' \
      > /etc/profile.d/99-board-toolchain.sh \
    && chmod 644 /etc/profile.d/99-board-toolchain.sh \
    && chown -R root:root /opt/verifier-venv /usr/local/go /usr/local/cargo /usr/local/rustup \
    && chmod -R go-w /opt/verifier-venv \
    && chmod go-w /opt/verifier-venv/bin /opt/verifier-venv/bin/pytest

ENV PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/app/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RUN cd /app/environment \
    && go build -o /app/bin/boardctl ./cmd/boardctl

WORKDIR /app
CMD ["bash"]
