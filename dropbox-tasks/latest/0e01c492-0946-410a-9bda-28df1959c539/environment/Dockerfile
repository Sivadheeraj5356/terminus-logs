FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        gcc \
        libc6-dev \
        procps \
        tmux \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps -r /tmp/requirements.lock

ENV PYTHONUNBUFFERED=1

WORKDIR /app/reactor

COPY app/reactor /app/reactor

CMD ["sleep", "infinity"]
