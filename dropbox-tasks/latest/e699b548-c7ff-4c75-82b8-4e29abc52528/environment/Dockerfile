FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        asciinema \
        g++ \
        make \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir \
    pytest==9.0.3 \
    pytest-json-ctrf==0.5.0

ENV PATH="/opt/verifier-venv/bin:${PATH}"

WORKDIR /app

RUN mkdir -p /app/state

COPY app/ /app/

RUN make clean all

RUN printf 'set +e\n' > /root/.bashrc \
 && mkdir -p /root/.config/tmux \
 && printf 'set -g remain-on-exit on\nset-hook -g pane-died "respawn-pane"\n' > /root/.tmux.conf
