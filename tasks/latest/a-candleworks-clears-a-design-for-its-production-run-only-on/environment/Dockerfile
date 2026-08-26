# The deliverable is Rust, so the image starts from the sanctioned canonical rust base. Grading runs
# with the network off (allow_internet=false), so the tools the base does not carry -- make (which
# drives the Makefile), python3 (the pytest runtime), and tmux plus asciinema (the session recorder)
# -- are laid down from arch-matched .debs vendored under environment/debs/ rather than apt, and the
# pytest verifier lives in a hash-pinned virtualenv built from vendored wheels. Build and grade both
# stay fully offline.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

# build-rev r1 2026-07-19 cache-bust for the R1 instruction sufficiency revision (comment only, image unchanged)
ENV DEBIAN_FRONTEND=noninteractive
# Only the bundled standard library is linked: no external crates, no cargo registry traffic, so the
# compile stays offline.
ENV CARGO_NET_OFFLINE=true
# Pin the rustup toolchain paths so the agent session and the verifier subprocess both find the same
# rustc/cargo the image was built with.
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo

WORKDIR /app

# Lay down make/tmux and the python3 runtime from the vendored .debs. dpkg runs twice because
# python3-minimal pre-depends on python3.11-minimal, which must configure on the first pass before
# python3-minimal can unpack on the second; a command check then confirms the toolchain landed and
# the stdlib modules the verifier leans on all import.
COPY debs/ /tmp/debs/
RUN A="$(dpkg --print-architecture)" \
 && dpkg -i /tmp/debs/"$A"/*.deb >/dev/null 2>&1 || true \
 && dpkg -i /tmp/debs/"$A"/*.deb >/dev/null 2>&1 || true \
 && dpkg --configure -a >/dev/null 2>&1 || true \
 && rm -rf /tmp/debs \
 && command -v make >/dev/null && command -v tmux >/dev/null \
 && python3 -c "import ssl, sqlite3, ctypes, venv, subprocess, json, hashlib"

# A tmux login shell rebuilds PATH from /etc/profile and drops /usr/local/cargo/bin, so symlink the
# toolchain into /usr/local/bin, which stays on PATH. That keeps make/rustc reachable both
# interactively and from the verifier subprocess.
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

# The image default user stays root. The platform's environment-start step execs the mounted work
# directories as the image's default user, and a non-root default there stalls that startup, so no
# USER directive is set. Anti-cheat does not lean on the agent session's user: the verifier makes its
# own drop to an unprivileged account when it reseals, rebuilds, and grades in an isolated tree.
COPY Makefile /app/environment/Makefile
COPY main.rs /app/environment/main.rs
COPY data/ /app/environment/data/

# Compile once at build time so the binary is present and the toolchain is proven to link offline
# before any grading run.
RUN make -C /app/environment
