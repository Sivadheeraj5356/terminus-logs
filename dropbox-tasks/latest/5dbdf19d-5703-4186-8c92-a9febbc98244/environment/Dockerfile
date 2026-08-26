FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV PATH="/opt/verifier-venv/bin:${PATH}"
ENV NODE_ENV=development

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv && \
    /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==9.0.3 \
        pytest-json-ctrf==0.5.0

COPY package.json tsconfig.json /app/
RUN npm install --save-dev --no-package-lock typescript@5.4.5 @types/node@20.14.2

COPY logs/ /app/logs/

RUN mkdir -p /app/src /app/dist /var/tmp/tmux && chmod 1777 /var/tmp/tmux

WORKDIR /app
