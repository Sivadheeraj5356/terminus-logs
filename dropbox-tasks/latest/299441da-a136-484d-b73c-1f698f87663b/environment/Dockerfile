# Final stage is canonical Debian. Julia is not on the Terminal-Bench canonical
# base list, so the toolchain is installed from a pinned julia.lock tarball
# (Julia 1.11.x) during the builder stage and copied into the runtime image.

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20230311+deb12u1 \
    curl=7.88.1-10+deb12u15 \
    gcc=4:12.2.0-3 \
    libc6-dev=2.36-9+deb12u14 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    && rm -rf /var/lib/apt/lists/*

COPY julia.lock /tmp/julia.lock
COPY requirements.lock /tmp/requirements.txt

RUN set -eux; \
    jver="$(grep '^JULIA_VERSION=' /tmp/julia.lock | cut -d= -f2)"; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) \
        jurl="$(grep '^JULIA_URL_X86_64=' /tmp/julia.lock | cut -d= -f2)"; \
        jsha="$(grep '^JULIA_SHA256_X86_64=' /tmp/julia.lock | cut -d= -f2)" ;; \
      arm64) \
        jurl="$(grep '^JULIA_URL_AARCH64=' /tmp/julia.lock | cut -d= -f2)"; \
        jsha="$(grep '^JULIA_SHA256_AARCH64=' /tmp/julia.lock | cut -d= -f2)" ;; \
      *) echo "unsupported arch: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "$jurl" -o /tmp/julia.tar.gz; \
    echo "${jsha}  /tmp/julia.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/julia.tar.gz -C /opt; \
    mv "/opt/julia-${jver}" /usr/local/julia

ENV PATH="/usr/local/julia/bin:${PATH}"

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps \
        -r /tmp/requirements.txt

COPY wit_q /build/wit_q
RUN gcc -shared -fPIC -O2 -o /build/wit_q/libkq_wit.so /build/wit_q/witbit.c

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV JULIA_DEPOT_PATH=/opt/julia_depot
ENV JULIA_PKG_PRECOMPILE_AUTO=0
ENV PATH="/opt/verifier-venv/bin:/app/environment/tools:/usr/local/julia/bin:${PATH}"

WORKDIR /app

COPY --from=builder /usr/local/julia /usr/local/julia
COPY --from=builder /opt/verifier-venv /opt/verifier-venv
COPY --from=builder /build/wit_q/libkq_wit.so /app/environment/wit_q/libkq_wit.so

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    binutils=2.40-2 \
    ca-certificates=20230311+deb12u1 \
    libgomp1=12.2.0-14+deb12u1 \
    libopenblas0=0.3.21+ds-4 \
    libstdc++6=12.2.0-14+deb12u1 \
    ncurses-term=6.4-4 \
    python3=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux /opt/julia_depot /app/output /app/environment/wit_q \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/tmux.conf /etc/tmux.conf
COPY Project.toml Manifest.toml /app/environment/
COPY src /app/environment/src
COPY kep_a /app/environment/kep_a
COPY molt_b /app/environment/molt_b
COPY rune_c /app/environment/rune_c
COPY volt_d /app/environment/volt_d
COPY bind_h /app/environment/bind_h
COPY frame_h /app/environment/frame_h
COPY auth_f /app/environment/auth_f
COPY lane_g /app/environment/lane_g
COPY zen_e /app/environment/zen_e
COPY deck_p /app/environment/deck_p
COPY docs /app/environment/docs
COPY tools /app/environment/tools
COPY wit_q/witbit.c wit_q/mk_witbit.sh /app/environment/wit_q/

RUN chmod +x /app/environment/tools/kq_run /app/environment/wit_q/mk_witbit.sh \
    && tmux -V && asciinema --version \
    && julia /app/environment/src/kq_handler.jl --deck /app/environment/deck_p/s0 --out /tmp/kq_smoke.json \
    && test -s /tmp/kq_smoke.json

WORKDIR /app
