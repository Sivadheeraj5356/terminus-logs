# Builder stage: Zig is not on the Terminal-Bench canonical language-runtime
# list, so this stage uses sanctioned ECR debian:bookworm-slim and installs a
# pinned Zig 0.13.0 tarball to compile the CipherGrid puzzle-league scorer.
# Final stage is canonical python:3.13-slim-bookworm with Graphviz for the
# board map digraph.

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d AS zig_builder

ENV DEBIAN_FRONTEND=noninteractive
ARG ZIG_VERSION=0.13.0

WORKDIR /tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        xz-utils \
    && arch="$(dpkg --print-architecture)" \
    && case "$arch" in \
         amd64) zig_arch="x86_64"; zig_sha="d45312e61ebcc48032b77bc4cf7fd6915c11fa16e4aad116b66c9468211230ea" ;; \
         arm64) zig_arch="aarch64"; zig_sha="041ac42323837eb5624068acd8b00cd5777dac4cf91179e8dad7a7e90dd0c556" ;; \
         *) echo "unsupported arch: $arch" >&2; exit 1 ;; \
       esac \
    && tarball="zig-linux-${zig_arch}-${ZIG_VERSION}.tar.xz" \
    && curl -fsSL -o /tmp/zig.tar.xz "https://ziglang.org/download/${ZIG_VERSION}/${tarball}" \
    && echo "${zig_sha}  /tmp/zig.tar.xz" | sha256sum -c - \
    && mkdir -p /opt \
    && tar -xJf /tmp/zig.tar.xz -C /opt \
    && mv "/opt/zig-linux-${zig_arch}-${ZIG_VERSION}" /opt/zig \
    && rm -f /tmp/zig.tar.xz \
    && rm -rf /var/lib/apt/lists/*

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

# Zig + Graphviz stay in the final image so the puzzle-league match can rebuild
# cipherleague offline when combo, rivalry, or echo scoring changes.
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/zig:/usr/local/bin:/app/bin:${PATH}"

WORKDIR /app

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        graphviz=2.42.2-7+deb12u1 \
        tmux=3.3a-3 \
        xz-utils=5.4.1-1+deb12u1 \
    && pip3 install --no-cache-dir --break-system-packages --require-hashes --no-deps \
        -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements.lock

COPY --from=zig_builder /opt/zig /opt/zig
RUN ln -sf /opt/zig/zig /usr/local/bin/zig

COPY --chmod=0755 build.sh /app/build.sh
COPY --chmod=0666 app/ /app/app/
COPY data/ /app/data/
COPY schema/ /app/schema/

RUN mkdir -p /app/bin /app/var \
    && chmod 0777 /app/bin /app/var \
    && chmod 0666 /app/app/src/*.zig \
    && bash /app/build.sh \
    && chmod 0755 /app/bin/cipherleague \
    && chmod 0666 /app/app/src/*.zig \
    && chmod 0777 /app/bin /app/var
