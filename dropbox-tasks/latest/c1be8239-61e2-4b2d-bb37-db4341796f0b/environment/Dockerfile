FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update && apt-get install -y --no-install-recommends \
        asciinema ca-certificates curl nodejs npm python3 python3-venv ripgrep tmux \
    && rm -rf /var/lib/apt/lists/* \
    && mv /usr/bin/apt-get /usr/bin/apt-get.disabled

COPY verifier-requirements.lock /tmp/verifier-requirements.lock
COPY verifier_wheels/ /tmp/verifier-wheels/
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-index --find-links /tmp/verifier-wheels \
        --no-cache-dir --require-hashes --no-deps -r /tmp/verifier-requirements.lock \
    && rm -rf /tmp/verifier-wheels /tmp/verifier-requirements.lock

RUN printf 'export PATH="$PATH:/usr/local/cargo/bin"\n' > /etc/profile.d/cargo.sh \
    && chmod 0644 /etc/profile.d/cargo.sh

WORKDIR /app/task_file/logseal
COPY task_file/logseal/Cargo.toml task_file/logseal/Cargo.lock ./
COPY task_file/logseal/src/main.rs src/main.rs
RUN cargo fetch --locked

WORKDIR /app
COPY task_file/ /app/task_file/

ENV CARGO_NET_OFFLINE=true \
    PATH=/usr/local/cargo/bin:$PATH

CMD ["sleep", "infinity"]
