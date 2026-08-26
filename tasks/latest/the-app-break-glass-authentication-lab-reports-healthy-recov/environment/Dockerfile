FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

COPY requirements.txt /tmp/requirements.txt
# Offline verifier roots (hash-locked above): pytest==8.4.1 pytest-json-ctrf==0.3.5

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
        asciinema \
        ca-certificates \
        libssl-dev \
        openssl \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/task-venv \
    && /opt/task-venv/bin/python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

ENV PATH="/opt/task-venv/bin:/app/bin:${PATH}"

WORKDIR /app
COPY . /app

RUN chmod +x /app/scripts/*.sh \
    && make -j2 \
    && /app/scripts/regenerate-policy.sh \
    && useradd --create-home --uid 1000 agent \
    && chown -R agent:agent /app

CMD ["/bin/bash"]
