FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

LABEL org.opencontainers.image.source="terminal-bench"
LABEL org.opencontainers.image.revision="local"
LABEL org.opencontainers.image.created="2026-06-13"
LABEL org.opencontainers.image.version="2.0"
LABEL org.opencontainers.image.licenses="Apache-2.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_DEFAULT_TIMEOUT=120

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      make \
      tmux \
      asciinema \
      python3 \
      python3-pip \
      python3-venv \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages 'uv==0.9.5'

RUN mkdir -p /opt/pytest-whl \
 && pip3 download \
        --disable-pip-version-check \
        -d /opt/pytest-whl \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

ENV PIP_NO_INDEX=1
ENV PIP_FIND_LINKS=/opt/pytest-whl

RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install \
        --disable-pip-version-check \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

WORKDIR /app

COPY Makefile /app/Makefile
COPY include/ /app/include/
COPY phase_h/ /app/phase_h/
COPY stencil_k/ /app/stencil_k/
COPY crate_q/ /app/crate_q/
COPY ridge_o/ /app/ridge_o/
COPY lattice_p/ /app/lattice_p/
COPY lib/ /app/lib/
COPY decoy/ /app/decoy/
COPY extras/ /app/extras/
COPY bracket/ /app/bracket/
COPY ci/ /app/ci/
COPY cfg/ /app/cfg/
COPY data/ /app/data/
COPY doc/ /app/doc/
COPY notes/ /app/notes/
COPY stubs/ /app/stubs/
COPY config/ /app/config/
COPY harness/ /app/harness/

RUN chmod +x /app/ci/build_and_load.sh \
 && mkdir -p /app/output /app/var/snapshots /app/bin

ENV TASK_APP_ROOT=/app
