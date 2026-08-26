# The project source is C, so the image is pinned to the sanctioned GCC base from the public.ecr.aws
# mirror by digest. Grading runs in a sandbox with no network, so every apt/pip fetch is swapped for
# arch-matched artifacts vendored in the tree and the whole image builds offline.
FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# gcc, make and python3 already ride in the base image; only tmux (which the session recorder drives)
# is absent, so it and its one missing runtime dependency, libutempter0, are laid down from the
# arch-matched .debs staged under environment/debs/ and configured in dependency order.
COPY debs/ /tmp/debs/
RUN dpkg -i /tmp/debs/"$(dpkg --print-architecture)"/*.deb \
 && rm -rf /tmp/debs

# The base python3 carries no ensurepip, so the verifier venv is made --without-pip and pip is
# bootstrapped from a vendored wheel. Every verifier dependency (pytest, asciinema, the ctrf plugin)
# is a pinned, hashed, pure-python wheel under environment/wheels/, installed --no-index so no PyPI
# access is needed. asciinema's launcher is linked onto PATH for the recorder.
COPY requirements.txt /tmp/requirements.txt
COPY wheels/ /tmp/wheels/
RUN python3 -m venv --without-pip /opt/verifier-venv \
 && /opt/verifier-venv/bin/python /tmp/wheels/pip-26.1.2-py3-none-any.whl/pip install \
      --no-cache-dir --no-index --find-links=/tmp/wheels \
      --require-hashes -r /tmp/requirements.txt \
 && ln -s /opt/verifier-venv/bin/asciinema /usr/local/bin/asciinema \
 && rm -rf /tmp/wheels /tmp/requirements.txt

# Create the unprivileged agent account and hand it the app tree without a recursive ownership change:
# pre-create the two app directories and set just their owner, then bring the sources in already owned by
# agent through COPY --chown. The harness starts the verifier with its own privileges, so grading (which
# rebuilds under an isolated account) is unaffected.
RUN useradd --create-home --shell /bin/bash agent \
 && mkdir -p /app/environment \
 && chown agent:agent /app /app/environment
COPY --chown=agent:agent Makefile /app/environment/Makefile
COPY --chown=agent:agent main.c /app/environment/main.c
COPY --chown=agent:agent data/ /app/environment/data/

# Build once at image time so the binary is present and the toolchain is proven to link offline before
# any grading run. The compile runs as the agent user and pulls in only the C standard library and libm.
RUN make -C /app/environment

# cache-bust r17 (2026-07-18): forces a fresh image build id (79a3e404 env-start-timeout @1800s, org Daytona outage)
