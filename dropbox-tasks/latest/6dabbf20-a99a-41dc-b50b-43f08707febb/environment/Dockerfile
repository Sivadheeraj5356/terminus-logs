FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive

# All dependency installation in one layer, before any source COPY, so source
# edits do not bust the dependency cache. The verifier-side numpy oracle and
# pytest are pinned. The agent compiles the Rust crate at runtime, so the Rust
# toolchain in the base image is required (single-stage by design).
RUN apt-get update && apt-get install -y --no-install-recommends \
      sqlite3 \
      python3 \
      python3-pip \
      tmux \
      asciinema \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages \
         numpy==2.1.3 \
         pytest==8.4.1

WORKDIR /app

# Starter repo only. Tests and the reference solution are never copied into the image.
COPY app/ /app/

CMD ["/bin/bash"]
