FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

# UTF-8 locale so asciinema/tmux start cleanly during agent setup
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

LABEL rebuild="2026-07-04-canonical-ecr-base-timeout1800"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    cryptography==42.0.8 \
    flask==3.0.3

WORKDIR /app

# Provide the demo manifest the milestone instructions reference at /app/data/manifest.json
# so the agent (not only the oracle) can canonicalize/sign/submit it.
COPY data/manifest.json /app/data/manifest.json

# Milestone 6 — NEUTRAL reverse-engineering evidence for the undocumented CT-log
# entry leaf-canonicalization. Only worked-example pairs (entry + its exact
# canonical bytes / leaf hash / signed_input / a valid signature), the log public
# key, an inventory, and a wire-shape format note ship into the image. The rule
# is NEVER stated and NO answer index / golden grading corpus is copied here:
# the full held-out golden corpus is test-private under steps/milestone_6/tests.
COPY provided/entrylog /app/transparency/entrylog
