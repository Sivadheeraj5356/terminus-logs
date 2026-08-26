FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN rm -rf /var/lib/apt/lists/* /var/cache/apt/* \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        make \
        tmux \
    && groupadd --system blender-profile \
    && useradd --system --gid blender-profile --home-dir /nonexistent --shell /usr/sbin/nologin blender-profile \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /wheels \
    && python3 -m pip wheel --no-cache-dir --wheel-dir /wheels \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    && python3 -m pip install --break-system-packages --no-index --find-links=/wheels \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY app/ /app/

RUN make
