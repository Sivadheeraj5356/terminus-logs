FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust_185

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

# The runtime intentionally retains Rust plus a linker because the scientific task
# requires the agent and verifier to compile a standalone Rust numerical solver.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       asciinema=2.2.0-1 \
       build-essential=12.9 \
       tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier
RUN /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt
RUN rm -f /tmp/requirements.txt

COPY --from=rust_185 /usr/local/cargo /usr/local/cargo
COPY --from=rust_185 /usr/local/rustup /usr/local/rustup

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/opt/verifier/bin:/usr/local/cargo/bin:${PATH}" \
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
    SOURCE_DATE_EPOCH=0

COPY toolchain_smoke.rs /tmp/toolchain_smoke.rs
RUN rustc --edition=2021 --crate-name toolchain_smoke /tmp/toolchain_smoke.rs -o /tmp/toolchain-smoke \
    && /tmp/toolchain-smoke \
    && rm -f /tmp/toolchain-smoke /tmp/toolchain_smoke.rs

COPY thermal_problem /app/thermal_problem
RUN mkdir -p /app/thermal_mode_results
