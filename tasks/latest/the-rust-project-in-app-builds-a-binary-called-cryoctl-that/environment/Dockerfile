FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

# System tooling: harness requirements (tmux, asciinema), shell + util-linux,
# agent search/edit tools, patch, and Python for the pytest-based verifier.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        git \
        patch \
        python3 \
        python3-pip \
        ripgrep \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

# The agent runs in a login shell that resets PATH and drops Docker ENV PATH
# additions, so symlink the Rust toolchain into /usr/local/bin to keep cargo and
# rustc visible.
RUN ln -sf "$(command -v cargo)" /usr/local/bin/cargo \
    && ln -sf "$(command -v rustc)" /usr/local/bin/rustc

# Pinned, hash-locked verifier dependencies (pytest + ctrf reporter), installed
# into the image's system Python. Provide a `python` alias so `python -m pytest`
# resolves in the verifier script.
COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock \
    && ln -sf /usr/bin/python3 /usr/local/bin/python

WORKDIR /app

# Bring the Cargo manifests first so the dependency layer caches well, then warm
# the dependency graph against an empty crate so the registry/index download is
# cached independently of the task source.
COPY repo/Cargo.toml repo/Cargo.lock /app/
RUN mkdir -p src \
    && echo 'fn main() {}' > src/main.rs \
    && cargo build --release \
    && rm -rf src

# Bring the source and warm the real build: compile the unmodified repo and
# leave a runnable binary at /app/cryoctl. The agent's later rebuild is then
# incremental. target/ and the cargo registry cache are kept in the image.
COPY repo/ /app/
# Drop the empty-crate warm-build artifacts (binary + fingerprint) and refresh the
# real source mtime so Cargo cannot mistake the placeholder build for up-to-date and
# skip recompiling; otherwise build.sh would copy the stale empty binary.
RUN rm -f /app/target/release/cryoctl \
    && rm -rf /app/target/release/.fingerprint \
    && find /app/src -type f -exec touch {} + \
    && chmod +x /app/build.sh \
    && /app/build.sh

# Expose the launcher at /app/cryoctl as documented in instruction.md.
RUN ln -sf /app/cryoctl /usr/local/bin/cryoctl

# Initialize a git repo inside the image so the agent's edit/diff tooling works.
RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
