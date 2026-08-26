# Canonical Terminal-Bench final base: C/C++ (GCC) bookworm digest.
FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

WORKDIR /app

ENV PATH=/opt/verifier/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    cmake=3.25.1-1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-randomly==3.16.0

RUN mkdir -p /app/environment /app/output /logs/verifier

COPY . /app/environment

RUN chmod +x /app/environment/scripts/bake_ws.sh \
    && chmod +x /app/environment/migrations/wipe7.sh \
    && /app/environment/scripts/bake_ws.sh

CMD ["sleep", "infinity"]
