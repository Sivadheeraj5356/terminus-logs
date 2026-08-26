# Standard ML has no canonical base image, so this rebases on the canonical
# Debian row and installs the toolchain itself, as the base-image policy directs
# for languages outside the published list. MLton was dropped from Debian
# bookworm (no apt candidate), so the official pinned static release is vendored
# alongside this file and unpacked here: the build sandbox cannot reach
# github.com, so fetching it at build time is not an option.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d AS mlton

COPY mlton-20241230-1.amd64-linux.ubuntu-22.04_static.tgz /tmp/mlton.tgz
COPY mlton.sha256 /tmp/mlton.sha256
RUN cd /tmp \
    && sha256sum -c mlton.sha256 \
    && mkdir -p /opt/mlton \
    && tar -xzf mlton.tgz --strip-components=1 -C /opt/mlton \
    && rm -f mlton.tgz mlton.sha256

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d
LABEL org.opencontainers.image.title="protein-folding-rare-transition-sml"

# gcc and libc6-dev are runtime deps, not build deps: MLton shells out to the C
# compiler on every compile, and the agent compiles. gcc only Recommends
# libc6-dev, so with --no-install-recommends it has to be named explicitly or
# MLton's cc step cannot find assert.h.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        gcc \
        libc6-dev \
        libgmp-dev \
        python3 \
        python3-pip \
        python-is-python3 \
        sqlite3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Verifier dependencies. The verifier has no network, so they are baked in.
RUN python -m pip install --no-cache-dir --break-system-packages \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

# The bin/mlton wrapper derives its library path from its own location and does
# not resolve symlinks, so put it on PATH rather than linking into /usr/local/bin.
COPY --from=mlton /opt/mlton /opt/mlton
ENV PATH=/opt/mlton/bin:$PATH

WORKDIR /app

COPY MODEL.md /app/MODEL.md
COPY src/ /app/src/
COPY --chmod=0755 build.sh /app/build.sh
COPY --chmod=0755 run.sh /app/run.sh

# Assemble the study database from the per-molecule seeds, then drop the seeds:
# the study ships as the database, not as a pile of SQL.
COPY seed/ /tmp/seed/
RUN mkdir -p /app/data /app/output \
    && cat /tmp/seed/schema.sql /tmp/seed/config.sql /tmp/seed/molecule_*.sql \
       | sqlite3 /app/data/study.sqlite \
    && test "$(sqlite3 /app/data/study.sqlite 'SELECT count(*) FROM config')" = 1 \
    && test "$(sqlite3 /app/data/study.sqlite 'SELECT count(*) FROM observations')" = 100 \
    && rm -rf /tmp/seed

RUN /app/build.sh
