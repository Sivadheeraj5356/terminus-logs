# Canonical Terminal-Bench Rust runtime (digest-pinned) for cargo/rustc rebuild of /app/tb3.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    strace=6.1-0.1 \
    tmux=3.3a-3 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 --shell /usr/sbin/nologin agent

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

ENV PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:${PATH}"
ENV CARGO_INCREMENTAL=0
ENV TB3_AGENT_UID=10001
ENV TB3_AGENT_GID=10001

COPY --chown=agent:agent app /app

RUN chmod +x /app/scripts/build.sh \
 && /app/scripts/build.sh \
 && chown agent:agent /app /app/bin /app/state /app/out \
 && find /app/target /app/bin /app/tb3 /app/scripts -exec chown agent:agent {} + \
 && chown root:root /app/data /app/config \
 && find /app/data /app/config -type d -exec chmod 555 {} + \
 && find /app/data /app/config -type f -exec chmod 444 {} + \
 && find /app/data /app/config -exec chown root:root {} + \
 && mkdir -p /opt/verifier-fixtures \
 && chown root:root /opt/verifier-fixtures \
 && chmod 755 /opt/verifier-fixtures

WORKDIR /app

