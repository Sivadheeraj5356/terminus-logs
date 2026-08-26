# Reproducible, pin-locked build. Every dependency source below is fixed to an
# immutable, content-addressed mirror, so a rebuild resolves byte-identical
# packages no matter when it runs:
#   - the base image is digest-pinned (FROM ...@sha256:...);
#   - Debian/apt OS packages come from a dated snapshot.debian.org archive;
#   - R packages come from a dated Posit Package Manager snapshot, and each
#     resolved version is asserted so any drift fails the build;
#   - the verifier's Python wheels are installed --require-hashes from the
#     committed requirements.lock, so every wheel is checked against a pinned hash.
# The build fetches these fixed artifacts from their immutable mirrors; nothing
# resolves against a live/rolling index. The task RUNTIME is fully offline: no
# package index is reached while the agent's solution or the verifier runs.
#
# The canonical base-image registry has no R image, so the sanctioned Python
# base is used and R is added from apt below: it supplies the agent's R runtime
# and the Python venv that the verifier runs pytest in.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Pin the Debian apt repositories to an immutable snapshot.debian.org date so the
# OS packages below resolve to fixed versions on every rebuild. This is the
# reproducible alternative to per-package `pkg=version` pins, which silently
# break once the rolling bookworm repo drops an old version. The snapshot date is
# chosen to match the digest-pinned base image's build date (2026-03-16) so the
# snapshot's package versions are consistent with those already installed in the
# base image; bookworm-updates and bookworm-security are included for the same
# reason.
RUN printf '%s\n' \
      'Types: deb' \
      'URIs: https://snapshot.debian.org/archive/debian/20260317T000000Z' \
      'Suites: bookworm bookworm-updates' \
      'Components: main' \
      'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
      'Check-Valid-Until: no' \
      '' \
      'Types: deb' \
      'URIs: https://snapshot.debian.org/archive/debian-security/20260317T000000Z' \
      'Suites: bookworm-security' \
      'Components: main' \
      'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
      'Check-Valid-Until: no' \
      > /etc/apt/sources.list.d/debian.sources && \
    rm -f /etc/apt/sources.list && \
    apt-get -o Acquire::Retries=5 update -qq && \
    apt-get install -y --no-install-recommends \
      asciinema \
      ca-certificates \
      libgomp1 \
      r-base \
      r-base-dev \
      tmux && \
    rm -rf /var/lib/apt/lists/*

# Install the R packages from a date-pinned Posit Package Manager snapshot and
# assert the exact resolved versions, so the R dependency set is reproducible
# and any drift fails the build.
RUN R -e "options(repos = 'https://packagemanager.posit.co/cran/__linux__/bookworm/2025-01-15'); \
    want <- c(jsonlite = '1.8.9'); \
    install.packages(names(want), Ncpus = 2); \
    for (p in names(want)) { \
      if (!requireNamespace(p, quietly = TRUE)) { message('R PACKAGE FAILED TO INSTALL: ', p); quit(status = 1L) }; \
      got <- as.character(packageVersion(p)); \
      if (got != want[[p]]) { message('R PACKAGE VERSION MISMATCH: ', p, ' got ', got, ' want ', want[[p]]); quit(status = 1L) } \
    }; \
    message('R packages pinned: ', paste(names(want), want, sep = ' ', collapse = ', '))"

RUN python3 -m venv /opt/test-venv

# Hash-locked, dependency-frozen install: --require-hashes verifies every wheel
# against the SHA256 pinned in requirements.lock and --no-deps forbids resolving
# anything not listed, so the verifier's Python environment is fully reproducible.
COPY requirements.lock /tmp/requirements.lock
RUN /opt/test-venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app
RUN mkdir -p /app/outputs

COPY data/ /app/data/
COPY contracts/ /app/contracts/
