# Canonical sanctioned Java base image (digest-pinned)
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

WORKDIR /app

LABEL task="mode-consolidation-histogram-profiler"
ENV TASK_BUILD_REV="mchp-consolidate-1"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        ca-certificates \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Unprivileged account the verifier uses to run the candidate binary so it
# cannot read the test harness or the reference implementation.
RUN useradd --system --no-create-home --shell /usr/sbin/nologin candidate

# Pytest verifier runtime, fully hash-pinned into an isolated venv; the
# lockfile freezes the whole dependency graph by sha256.
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        --require-hashes --no-deps -r /tmp/requirements.lock
ENV PATH="/opt/venv/bin:${PATH}"

COPY app/ /app/
