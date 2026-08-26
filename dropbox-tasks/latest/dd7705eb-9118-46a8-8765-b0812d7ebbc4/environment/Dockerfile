FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app
ENV PATH="/usr/local/cargo/bin:${PATH}"

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        ca-certificates \
        python3 \
        python3-pip \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/local/rustup/toolchains/1.85.1-$(uname -m)-unknown-linux-gnu/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/rustup/toolchains/1.85.1-$(uname -m)-unknown-linux-gnu/bin/rustc /usr/local/bin/rustc

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages --require-hashes --no-deps -r /tmp/requirements.lock

COPY task_file /app/task_file
RUN mkdir -p /app/task_file/output_data

RUN cd /app/task_file/backupplanner \
    && cargo fetch \
    && cargo build --release \
    && rm -rf target/release/backupplanner target/release/deps/backupplanner-*
