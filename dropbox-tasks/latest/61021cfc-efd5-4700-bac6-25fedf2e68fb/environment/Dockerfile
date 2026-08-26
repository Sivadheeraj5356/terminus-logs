# Multi-stage: compile rescue stack in builder; final image keeps gcc so agents can rebuild.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends make=4.3-4.1 build-essential=12.9 \
    libssl-dev=3.0.20-1~deb12u2 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY . /build/environment
RUN bash /build/environment/scripts/build_all.sh

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends make=4.3-4.1 build-essential=12.9 \
    libssl-dev=3.0.20-1~deb12u2 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY . /app/environment
COPY --from=builder /build/environment/bx7/libbx7.a /app/environment/bx7/libbx7.a
COPY --from=builder /build/environment/lw3/liblw3.a /app/environment/lw3/liblw3.a
COPY --from=builder /build/environment/dm5/libdm5.a /app/environment/dm5/libdm5.a
COPY --from=builder /build/environment/tools/rk_pack/rk_pack /app/environment/tools/rk_pack/rk_pack
COPY --from=builder /build/environment/tools/arena_ctl/arena_ctl /app/environment/tools/arena_ctl/arena_ctl

RUN mkdir -p /app/output \
    && chmod +x /app/environment/scripts/build_all.sh \
    && chmod +x /app/environment/migrations/mig_rst.sh \
    && chmod +x /app/environment/tools/rk_pack/rk_pack \
    && chmod +x /app/environment/tools/arena_ctl/arena_ctl

ENV PATH="/app/environment/tools/rk_pack:/app/environment/tools/arena_ctl:${PATH}"
ENV PYTHONPATH=/app
