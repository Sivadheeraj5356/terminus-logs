FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb AS builder

COPY verifier-deps.txt /tmp/verifier-deps.txt
RUN python3 -m venv /opt/verifier
RUN /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/verifier-deps.txt
RUN rm -f /tmp/verifier-deps.txt

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

ENV PATH=/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update && apt-get install -y --no-install-recommends asciinema=2.2.0-1 binutils=2.40-2 build-essential=12.9 ca-certificates=20230311+deb12u1 clang=1:14.0-55.7~deb12u1 cmake=3.25.1-1 lld=1:14.0-55.7~deb12u1 llvm=1:14.0-55.7~deb12u1 ninja-build=1.11.1-2~deb12u1 python3-venv=3.11.2-1+b1 tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && tmux -V \
    && asciinema --version

COPY --from=builder /opt/verifier /opt/verifier

ENV PYTHONPATH=/app/environment

COPY src /app/environment/src
COPY gen /app/environment/gen
COPY compile /app/environment/compile
COPY lto /app/environment/lto
COPY auxiliary /app/environment/auxiliary
COPY probes /app/environment/probes
COPY ci /app/environment/ci
COPY scripts /app/environment/scripts
COPY docs /app/environment/docs

RUN chmod +x /app/environment/compile/ninja_wrap.sh \
    /app/environment/scripts/reset_workspace.sh \
    /app/environment/ci/harness/*.sh \
    /app/environment/ci/fake_bin/clang-wrap \
    && ln -sf clang-wrap /app/environment/ci/fake_bin/clang \
    && ln -sf clang-wrap /app/environment/ci/fake_bin/clang++
