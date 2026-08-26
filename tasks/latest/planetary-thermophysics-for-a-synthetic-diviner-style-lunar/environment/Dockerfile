FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

# Canonical Terminal-Bench Rust runtime (see docs/creating-tasks/dockerfile-best-practices.md
# sanctioned list entry for Rust). Digest-pinned; not a non-canonical substitute.
# Root runtime only (no non-root USER). No image-time crate compile.
# Leave the default shell entry path unset; keep CMD sleep infinity for
# Daytona/Harbor boot.

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    python3 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Verifier Python deps come only from the hashed lockfile (direct + transitive).
# requirements.in lists the direct pins; requirements.lock pins every package
# with sha256 hashes. Install with --require-hashes --no-deps so nothing is
# resolved outside the submitted lock.
COPY requirements.in /tmp/requirements.in
COPY requirements.lock /tmp/requirements.lock

RUN pip3 install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps \
    -r /tmp/requirements.lock \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && rm -f /tmp/requirements.in /tmp/requirements.lock

COPY app /app

WORKDIR /app

ENV PATH="/app/target/release:/usr/local/cargo/bin:/root/.cargo/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

# Daytona/Harbor mount targets must exist and be writable before env start.
RUN mkdir -p \
      /logs/verifier \
      /logs/agent \
      /app/output \
    && chmod 0777 \
      /logs \
      /logs/verifier \
      /logs/agent \
      /app/output

CMD ["sleep", "infinity"]
