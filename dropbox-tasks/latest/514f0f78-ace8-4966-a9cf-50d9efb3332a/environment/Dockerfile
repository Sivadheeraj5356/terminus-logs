FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

WORKDIR /app

COPY requirements.lock /tmp/requirements.lock
COPY caption-verifier-wheels/ /tmp/caption-verifier-wheels/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        cmake=3.25.1-1 \
        patch=2.7.6-7 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
    && python3 -m venv /opt/verifier_venv \
    && /opt/verifier_venv/bin/pip install --no-cache-dir --no-index \
        --find-links=/tmp/caption-verifier-wheels \
        --require-hashes \
        --no-deps \
        -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache/pip /tmp/caption-verifier-wheels /tmp/requirements.lock

ENV PATH="/opt/verifier_venv/bin:${PATH}"

COPY caption-beam-kernel/ /app/

RUN chmod +x /app/rehearse_caption_beam.sh \
    && /app/rehearse_caption_beam.sh \
    && test -f /app/build/caption-beam \
    && test -d /app/decoder-notes
