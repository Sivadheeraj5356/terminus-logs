# Canonical Python slim runtime for pytest; build-essential + FFTW for agent C++ work.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update && apt-get install -y --no-install-recommends tmux=3.3a-3 asciinema=2.2.0-1 ca-certificates=20230311+deb12u1 build-essential=12.9 g++=4:12.2.0-3 make=4.3-4.1 libfftw3-dev=3.3.10-1 && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

WORKDIR /app
COPY Makefile /app/environment/
COPY config/ /app/environment/config/
COPY docs/ /app/environment/docs/
COPY fixtures/ /app/environment/fixtures/
COPY include/ /app/environment/include/
COPY lib/ /app/environment/lib/
COPY mesh/ /app/environment/mesh/
COPY src/ /app/environment/src/
COPY tools/ /app/environment/tools/

RUN make -C /app/environment/tools \
    && mkdir -p /app/environment/data/ct \
    && /app/environment/tools/gen_ct /app/environment/data/ct \
    && make -C /app/environment

RUN mkdir -p /app/data/ct /app/output/reports /app/state \
    && cp /app/environment/data/ct/*.ctb /app/data/ct/ \
    && ln -sf /app/environment/docs /app/docs
