# Digest-pinned Rust 1.85 image from the current Terminus canonical image set.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/verifier/bin:${PATH}" \
    CARGO_TARGET_DIR="/app/target"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        patch=2.7.6-7 \
        python3=3.11.2-1+b1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
    && python3 -m venv /opt/verifier \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
COPY vendor/wheels/ /opt/wheels/
RUN /opt/verifier/bin/pip install --no-index --find-links=/opt/wheels --no-deps --require-hashes -r /tmp/requirements.txt
RUN rm -rf /opt/wheels /tmp/requirements.txt /root/.cache

WORKDIR /app
COPY Cargo.toml Cargo.lock /app/environment/
COPY src/ /app/environment/src/
COPY docs/ /app/docs/
COPY data/ /app/data/
COPY check.sh /app/environment/check.sh

RUN chmod 0755 /app/environment/check.sh \
    && /app/environment/check.sh \
    && mkdir -p /app/output \
    && command -v cargo \
    && command -v rustc \
    && command -v tmux \
    && command -v asciinema

CMD ["bash"]
