FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        binutils \
        ca-certificates \
        file \
        less \
        patch \
        procps \
        python-is-python3 \
        python3 \
        python3-pip \
        python3-venv \
        ripgrep \
        strace \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /opt/requirements.lock
RUN python -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /opt/requirements.lock

COPY task_file/ /
RUN chmod 0755 /opt/linkseal/bin/linkseal \
    && ln -s /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -s /usr/local/cargo/bin/cargo /usr/local/bin/cargo

ENV CARGO_NET_OFFLINE=true \
    PATH=/opt/verifier-venv/bin:$PATH \
    PIP_NO_INDEX=1

WORKDIR /opt/linkseal
