FROM public.ecr.aws/docker/library/ruby:3.3-slim-bookworm@sha256:e76733e94b3a5893e4a141024ef3a583dc10781dc24becebf74f9c9f9a33e3df

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        patch \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY verifier-requirements.lock /environment/verifier-requirements.lock
COPY verifier-wheels /verifier-wheels
RUN python3 -m venv /opt/verifier_venv \
    && /opt/verifier_venv/bin/pip install --no-index --find-links=/verifier-wheels \
        -r /environment/verifier-requirements.lock \
    && /opt/verifier_venv/bin/python -m pytest --version \
    && /opt/verifier_venv/bin/python -m pytest --help | grep -q -- '--ctrf' \
    && ruby -v \
    && tmux -V \
    && asciinema --version \
    && rm -rf /verifier-wheels

WORKDIR /app
COPY app/ ./
RUN bash build.sh
