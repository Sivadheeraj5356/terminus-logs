FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

ARG ZIG_VERSION=0.14.0
ARG ZIG_SHA256=473ec26806133cf4d1918caf1a410f8403a13d979726a9045b421b685031a982

RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates=20230311+deb12u1 \
  curl=7.88.1-10+deb12u14 \
  python3-venv=3.11.2-1+b1 \
  tmux=3.3a-3 \
  asciinema=2.2.0-1 \
  xz-utils=5.4.1-1 \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://ziglang.org/download/${ZIG_VERSION}/zig-linux-x86_64-${ZIG_VERSION}.tar.xz" -o /tmp/zig.tar.xz \
  && echo "${ZIG_SHA256}  /tmp/zig.tar.xz" | sha256sum -c - \
  && mkdir -p /usr/local/zig \
  && tar -xJf /tmp/zig.tar.xz -C /usr/local/zig --strip-components=1 \
  && rm /tmp/zig.tar.xz

ENV PATH=/opt/verifier/bin:/usr/local/zig:${PATH}

RUN python3 -m venv /opt/verifier
RUN /opt/verifier/bin/pip install --no-cache-dir \
  pytest==8.4.1 \
  pytest-json-ctrf==0.3.5 \
  cryptography==44.0.2

COPY build.zig /app/build.zig
COPY build.zig.zon /app/build.zig.zon
COPY src /app/src
COPY config /app/config
COPY data /app/data
COPY docs /app/docs
COPY README.md /app/README.md
COPY tools /app/tools

RUN /usr/local/zig/zig build -Doptimize=ReleaseSafe
RUN mkdir -p /app/output /app/bin \
  && cp /app/zig-out/bin/quorumgate /app/bin/quorumgate
