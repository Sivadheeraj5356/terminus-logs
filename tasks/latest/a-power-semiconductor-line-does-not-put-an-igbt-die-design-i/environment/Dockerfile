# The agent writes Rust, so the image is built on the canonical rust base from the sanctioned set.
# The grade sandbox runs with no network (allow_internet=false), so the tools the base image lacks --
# make (drives the Makefile), python3 (the pytest verifier runtime), tmux and asciinema (the session
# recorder) -- are installed from arch-matched .debs vendored under environment/debs/ rather than apt,
# and the pytest verifier rides in a hash-pinned virtualenv built from vendored wheels. Both build and
# grade therefore stay fully offline.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive
# The build links only against the bundled standard library: no external crates, no cargo registry
# traffic, so compilation stays offline.
ENV CARGO_NET_OFFLINE=true
# Pin the rustup toolchain location so it stays reachable from every account the harness uses.
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo

WORKDIR /app

# Lay down make/tmux and the python3 runtime from the vendored .debs. dpkg runs twice because
# python3-minimal pre-depends on python3.11-minimal, which has to be configured on the first pass
# before python3-minimal can unpack on the second; a command check then asserts the toolchain landed
# and the stdlib modules the verifier relies on all import.
COPY debs/ /tmp/debs/
RUN A="$(dpkg --print-architecture)" \
 && dpkg -i /tmp/debs/"$A"/*.deb >/dev/null 2>&1 || true \
 && dpkg -i /tmp/debs/"$A"/*.deb >/dev/null 2>&1 || true \
 && dpkg --configure -a >/dev/null 2>&1 || true \
 && rm -rf /tmp/debs \
 && command -v make >/dev/null && command -v tmux >/dev/null \
 && python3 -c "import ssl, sqlite3, ctypes, venv, subprocess, json, hashlib"

# Under a tmux login shell PATH is rebuilt from /etc/profile and /usr/local/cargo/bin drops off it,
# so symlink the toolchain into /usr/local/bin (which stays on PATH). That keeps `make`/`rustc`
# reachable both interactively and from the verifier subprocess.
RUN ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
 && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo

# The vendored python3 ships no ensurepip, so the verifier venv is created --without-pip and pip is
# bootstrapped from a vendored wheel run directly. Every verifier dependency is a pinned, hashed,
# pure-python wheel under environment/wheels/, installed --no-index so the image builds with no PyPI
# access. asciinema's entry point is linked onto the default PATH.
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

# Compile once at build time so the binary is present and the toolchain is proven to link offline
# before any grading run.
RUN make -C /app/environment
