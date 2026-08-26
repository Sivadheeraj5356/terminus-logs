FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app
ENV PATH="/usr/local/bin:/usr/local/cargo/bin:/root/.cargo/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        less \
        nano \
        procps \
        python3 \
        python-is-python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*
RUN ln -sf "$(command -v rustc)" /usr/local/bin/rustc \
    && ln -sf "$(command -v cargo)" /usr/local/bin/cargo

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

COPY task_file/policy_case.txt /app/task_file/policy_case.txt
RUN rm -rf /app/task_file/output && mkdir -p /app/task_file/output
