# BASE_IMAGE_JUSTIFICATION: Pinned canonical AWS ECR gcc:13-bookworm for offline C
# binary cryogenic chamber thermodynamics (agent must rebuild after model edits).
FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

LABEL org.opencontainers.image.source="https://github.com/snorkel-ai/cryogenic-vacuum-stability-simulation"
LABEL org.opencontainers.image.description="N2/He Van der Waals mixture with sorption and freeze hysteresis"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        make \
        tmux \
        asciinema \
        python3 \
        python3-venv \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY verifier-requirements.lock /environment/verifier-requirements.lock
COPY verifier-wheels /verifier-wheels
RUN python3 -m venv /opt/verifier_venv \
    && /opt/verifier_venv/bin/pip install --no-index --no-deps --find-links=/verifier-wheels -r /environment/verifier-requirements.lock

WORKDIR /app

COPY app/ ./

RUN make -C /app clean all \
    && test -x /app/bin/cryovac

ENV PATH="/app/bin:${PATH}"
