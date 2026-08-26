FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

# Verifier-only deps: pytest to run the suite, playwright for browser-driven
# DOM/behavior checks against the agent's static page. The chromium browser
# and its runtime libraries are fetched at image build time so the verifier
# needs no network access at grading time.
RUN python -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    playwright==1.60.0 \
    && python -m playwright install --with-deps chromium

WORKDIR /app

# The binding policy is available to the agent inside the build environment.
COPY LINKOUT_POLICY.md /app/LINKOUT_POLICY.md
