FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --disable-pip-version-check \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

ENV PATH="/opt/venv/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
WORKDIR /app
COPY app/ /app/
