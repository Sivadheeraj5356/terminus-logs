FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-builder

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

ENV PATH="/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV CARGO_NET_OFFLINE=true
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -o Acquire::Retries=3 update -qq \
    && apt-get install -y -qq --no-install-recommends \
        asciinema=2.2.0-1 \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        file=1:5.44-3 \
        python-is-python3=3.11.2-1+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=rust-builder /usr/local/cargo /usr/local/cargo
COPY --from=rust-builder /usr/local/rustup /usr/local/rustup

RUN ln -sf /usr/bin/python3 /usr/local/bin/python \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustup /usr/local/bin/rustup \
    && ln -sf /usr/local/cargo/bin/cargo /usr/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustup /usr/bin/rustup

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps -r /tmp/requirements.txt

COPY cargo_warm/ /tmp/cargo_warm/
RUN mkdir -p /usr/local/cargo/vendor \
    && cp -a /tmp/cargo_warm/vendor/. /usr/local/cargo/vendor/ \
    && printf '%s\n' \
        '[source.crates-io]' \
        'replace-with = "vendored-sources"' \
        '' \
        '[source.vendored-sources]' \
        'directory = "/usr/local/cargo/vendor"' \
        > /usr/local/cargo/config.toml

COPY vendor_checksum_refresh.py /tmp/vendor_checksum_refresh.py
RUN python3 /tmp/vendor_checksum_refresh.py && rm -f /tmp/vendor_checksum_refresh.py

RUN rm -rf /tmp/cargo_warm/.cargo \
    && mkdir -p /tmp/cargo_warm/src \
    && printf '%s\n' 'fn main() {}' > /tmp/cargo_warm/src/main.rs \
    && cd /tmp/cargo_warm && cargo fetch \
    && rm -rf /tmp/cargo_warm \
    && test "$(find /usr/local/cargo/vendor -maxdepth 2 -name '.cargo-checksum.json' | wc -l)" -ge 9

COPY task_file/ /app/task_file/
COPY docs/ /app/docs/
COPY replay_tool_src/ /app/replay_tool_src/

RUN mkdir -p /app/bin /app/output

LABEL org.opencontainers.image.title="holdback_buffer_replay" \
      org.opencontainers.image.description="Offline JSONL holdback buffer lane-ledger replay environment" \
      org.opencontainers.image.source="holdback-buffer-replay" \
      org.opencontainers.image.revision="holdback_buffer_replay-revised-v26" \
      org.opencontainers.image.created="2026-07-19T00:00:00Z" \
      org.opencontainers.image.version="revised-v26" \
      org.opencontainers.image.licenses="UNLICENSED"

CMD ["bash"]
