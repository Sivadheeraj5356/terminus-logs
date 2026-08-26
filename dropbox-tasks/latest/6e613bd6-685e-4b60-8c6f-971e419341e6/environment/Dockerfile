FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

# The policy document and its four reference files are available to the
# agent alongside the pre-seeded, out-of-compliance rabbitmq_definitions.json
# it must fix. .rabbitmq_definitions.orig.json is a pristine, untouched copy
# used only by the oracle so it can rebuild its output deterministically no
# matter how many times it is run; it is not part of the graded deliverable.
COPY RABBITMQ_ACCESS_POLICY.md /app/RABBITMQ_ACCESS_POLICY.md
COPY PERMISSION_CHANGELOG.md /app/PERMISSION_CHANGELOG.md
COPY DOWNSTREAM_CONSUMERS.md /app/DOWNSTREAM_CONSUMERS.md
COPY PROTECTED_SERVICE_ACCOUNTS.md /app/PROTECTED_SERVICE_ACCOUNTS.md
COPY INCIDENT_ACCESS.md /app/INCIDENT_ACCESS.md
COPY rabbitmq_definitions.seed.json /app/rabbitmq_definitions.json
COPY rabbitmq_definitions.seed.json /app/.rabbitmq_definitions.orig.json
