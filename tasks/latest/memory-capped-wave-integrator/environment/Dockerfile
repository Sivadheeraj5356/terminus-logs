FROM node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

# Install python, pip, venv, tmux, asciinema
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

# Install python verifier packages
RUN python3 -m pip install --break-system-packages --no-cache-dir \
    pytest==8.3.4 \
    pytest-json-ctrf==0.3.5

WORKDIR /app
RUN mkdir -p /app/work
COPY . ./

