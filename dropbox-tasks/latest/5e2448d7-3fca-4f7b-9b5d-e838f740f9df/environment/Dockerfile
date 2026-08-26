FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust_base

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

# Agent session runtime — Harbor requires tmux and asciinema in every task image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        git=1:2.39.5-0+deb12u3 \
        pkg-config=1.8.1-1 \
        python-is-python3=3.11.2-1+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        sqlite3=3.40.1-2+deb12u2 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && command -v tmux \
    && command -v asciinema \
    && tmux -V \
    && asciinema --version

COPY --from=rust_base /usr/local/cargo /usr/local/cargo
COPY --from=rust_base /usr/local/rustup /usr/local/rustup

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH}"

RUN rustup default 1.85.0

COPY verifier-requirements.txt /tmp/verifier-requirements.txt
# Verifier packages: pytest==8.4.1 pytest-json-ctrf==0.3.5
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/verifier-requirements.txt
RUN rm -f /tmp/verifier-requirements.txt

WORKDIR /app

COPY go.mod /app/go.mod
COPY go.sum /app/go.sum
RUN go mod download

COPY rosegate/Cargo.toml /app/rosegate/Cargo.toml
COPY rosegate/src /app/rosegate/src
COPY rosegate/bearing_gate.h /app/rosegate/bearing_gate.h
COPY rosegate/bridge.go /app/rosegate/bridge.go

COPY pkg /app/pkg
COPY internal /app/internal
COPY cmd /app/cmd
COPY tools /app/tools
COPY scripts /app/scripts
COPY ci /app/ci
COPY docs /app/docs
COPY ops /app/ops
COPY profiles /app/profiles
COPY schemas /app/schemas
COPY harness /app/harness
COPY data /app/data
COPY README.md /app/README.md

RUN chmod +x /app/scripts/build.sh /app/ci/smoke.sh \
    && bash /app/scripts/build.sh

# Re-verify agent session tools after the compile step.
RUN command -v tmux \
    && command -v asciinema \
    && tmux new-session -d -s _agent_smoke \
    && tmux has-session -t _agent_smoke \
    && tmux kill-session -t _agent_smoke \
    && asciinema --version
