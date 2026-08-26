# The agent writes Rust, so the image is built on the canonical rust base from the sanctioned
# set. A hash-pinned virtualenv on top of the distribution python3 carries the pytest verifier,
# which runs with no network at grade time. The grading sandbox has no network, so the tools the
# rust base omits -- make (drives the Makefile), python3 (the pytest verifier runtime) and tmux
# (the session recorder) -- are vendored as arch-matched .debs under environment/debs/ rather than
# pulled by apt, and the verifier wheels are vendored under environment/wheels/, so both build and
# grade run fully offline.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

# build-rev: r3 (offline build: apt replaced by vendored debs + vendored pip; rev bumped on revise to force a fresh build)
ENV DEBIAN_FRONTEND=noninteractive
# The build links only against the bundled standard library: no external crates, no cargo
# registry traffic, so compilation stays offline.
ENV CARGO_NET_OFFLINE=true
# Pin the rustup toolchain location so the unprivileged agent user created below keeps the same
# rustc/cargo the root build used.
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo

WORKDIR /app

# Install the vendored toolchain from arch-matched .debs instead of apt. dpkg runs twice because
# python3-minimal pre-depends on python3.11-minimal, which has to be configured in the first pass
# before python3-minimal can unpack in the second; a command check then asserts the toolchain
# landed and that the python3 stdlib the verifier needs imports cleanly.
COPY debs/ /tmp/debs/
RUN A="$(dpkg --print-architecture)" \
 && dpkg -i /tmp/debs/"$A"/*.deb >/dev/null 2>&1 || true \
 && dpkg -i /tmp/debs/"$A"/*.deb >/dev/null 2>&1 || true \
 && dpkg --configure -a >/dev/null 2>&1 || true \
 && rm -rf /tmp/debs \
 && command -v make >/dev/null && command -v tmux >/dev/null \
 && python3 -c "import ssl, sqlite3, ctypes, venv, subprocess, json, hashlib"

# Under a tmux login shell PATH is rebuilt from /etc/profile and /usr/local/cargo/bin drops
# off it, so symlink the toolchain into /usr/local/bin (which stays on PATH). That keeps
# `make`/`rustc` reachable both interactively and from the verifier subprocess.
RUN ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
 && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo

# The base python3 ships no ensurepip, so the verifier venv is created --without-pip and pip is
# bootstrapped by running a vendored wheel directly. Every verifier dependency (pytest,
# pytest-json-ctrf, asciinema, ...) is a pinned, hashed, pure-python wheel under environment/wheels/,
# installed --no-index so the image builds with no PyPI access. asciinema's entry point is linked
# onto the default PATH.
COPY requirements.txt /tmp/requirements.txt
COPY wheels/ /tmp/wheels/
RUN python3 -m venv --without-pip /opt/verifier-venv \
 && /opt/verifier-venv/bin/python /tmp/wheels/pip-26.1.2-py3-none-any.whl/pip install \
      --no-cache-dir --no-index --find-links=/tmp/wheels \
      --require-hashes -r /tmp/requirements.txt \
 && ln -s /opt/verifier-venv/bin/asciinema /usr/local/bin/asciinema \
 && rm -rf /tmp/wheels /tmp/requirements.txt

COPY Makefile /app/environment/Makefile
COPY main.rs /app/environment/main.rs
COPY data/ /app/environment/data/

# Compile once at build time so the binary is present and the toolchain is proven to link
# offline before any grading run.
RUN make -C /app/environment

# Run the agent session as an unprivileged user instead of root: create `agent`, hand it /app and
# a home to work in, and leave the shared rust toolchain world-readable so it can still compile.
# The harness launches the verifier with its own privileges, so grading (which rebuilds under an
# isolated account) is unaffected.
RUN useradd --create-home --shell /bin/bash agent \
 && chown -R agent:agent /app \
 && chmod -R a+rX /usr/local/rustup /usr/local/cargo
