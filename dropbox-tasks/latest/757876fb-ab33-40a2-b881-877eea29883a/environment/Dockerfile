# Task-local exception and canonical-catalog proposal:
# /opt/foldpath/docs/base_image_exception.md
FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

# The terminal recorder requires a UTF-8 locale.  The native programs explicitly
# retain C numeric semantics (and C starts in the standard "C" locale until a
# program calls setlocale), so the harness can safely use C.UTF-8.
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates \
        iproute2 \
        less \
        make \
        nano \
        procps \
        psmisc \
        python3 \
        python3-pip \
        python3-venv \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

# Fail the image build instead of allowing the agent runner to discover a
# missing or locale-broken session dependency and attempt an online pip repair.
RUN test "$(locale charmap)" = "UTF-8" \
    && command -v tmux >/dev/null \
    && command -v asciinema >/dev/null \
    && timeout 5s tmux -V \
    && timeout 5s asciinema --version

COPY requirements.lock /tmp/foldpath-requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes \
        -r /tmp/foldpath-requirements.lock \
    && rm -f /tmp/foldpath-requirements.lock

WORKDIR /app
COPY Makefile /opt/foldpath/Makefile
COPY include/ /opt/foldpath/include/
COPY src/ /opt/foldpath/src/
COPY docs/ /opt/foldpath/docs/
COPY examples/ /opt/foldpath/examples/
COPY scripts/ /opt/foldpath/scripts/

RUN chmod 0755 /opt/foldpath/scripts/smoke.sh /opt/foldpath/scripts/check_contract.py \
    && make -C /opt/foldpath clean all install \
    && test -x /usr/local/bin/foldmodel-check
