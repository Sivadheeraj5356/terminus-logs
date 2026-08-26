# The agent writes Rust, so the image is built on the canonical rust base from the sanctioned
# set. A hash-pinned virtualenv on top of the distribution python3 carries the pytest verifier,
# which runs with no network at grade time.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive
# The build links only against the bundled standard library: no external crates, no cargo
# registry traffic, so compilation stays offline.
ENV CARGO_NET_OFFLINE=true

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      make \
      tmux \
      asciinema \
      python3 \
      python3-venv \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Under a tmux login shell PATH is rebuilt from /etc/profile and /usr/local/cargo/bin drops
# off it, so symlink the toolchain into /usr/local/bin (which stays on PATH). That keeps
# `make`/`rustc` reachable both interactively and from the verifier subprocess.
RUN ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
 && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

COPY Makefile /app/environment/Makefile
COPY main.rs /app/environment/main.rs
COPY data/ /app/environment/data/

# Compile once at build time so the binary is present and the toolchain is proven to link
# offline before any grading run.
RUN make -C /app/environment
