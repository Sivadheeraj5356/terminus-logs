FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        imagemagick=8:6.9.11.60+dfsg-1.6+deb12u12 \
        lua5.4=5.4.4-3+deb12u1 \
        sqlite3=3.40.1-2+deb12u2 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY app/ /app/

RUN mkdir -p /app/state /app/artifacts /app/.build \
    && chmod 0755 \
        /app/bin/clockwork-crypt \
        /app/bin/keeper-audit \
        /app/bin/rebuild-world \
        /app/tools/build_atlas.sh \
        /app/tools/canonical_dump.sh

WORKDIR /app
