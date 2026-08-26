FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update && apt-get install -y --no-install-recommends     tmux asciinema procps strace lsof     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Fully locked, hash-pinned install: every direct and transitive dependency
# is fixed to an exact version and verified against its known hashes, and pip
# is forbidden from resolving anything outside the lock.
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock     && rm /tmp/requirements.lock

# Unprivileged user the submitted recovery tool is executed as during
# grading. It has no access to verifier files and cannot inspect or attach to
# the game runtime daemon (which runs as root).
RUN useradd --no-create-home --uid 4001 --shell /usr/sbin/nologin glyphgrader

COPY game /app/glyph-mill
COPY build_runtime.py /tmp/build_runtime.py
COPY glyph-mill-wrapper /usr/local/bin/glyph-mill
COPY glyph-mill-entrypoint /usr/local/bin/glyph-mill-entrypoint

RUN python /tmp/build_runtime.py     && chmod +x /usr/local/bin/glyph-mill /usr/local/bin/glyph-mill-entrypoint     && rm /tmp/build_runtime.py

RUN python /app/glyph-mill/build_hint_store.py && rm /app/glyph-mill/build_hint_store.py

# The agent's shell (and the submitted tool, during grading) runs as
# glyphgrader for its whole session and must never be able to edit the
# fixtures it's supposed to be observing, or the CLI/interpreter binaries the
# verifier later trusts. Strip any group/other write bits explicitly rather
# than relying on COPY's default mode.
RUN find /app/glyph-mill /usr/local/bin/glyph-mill /usr/local/bin/glyph-mill-entrypoint -exec chmod go-w {} +

# test.sh scripts create /logs/verifier themselves — that path is reserved
# for Harbor's runtime mount, so it's not pre-created here.
RUN mkdir -p /app/recovered && chown glyphgrader:glyphgrader /app/recovered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/local/bin/glyph-mill-entrypoint"]
CMD ["bash"]
