FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages pytest==8.2.0

RUN mkdir -p /app /logs/verifier

WORKDIR /app

COPY Makefile /app/Makefile
COPY include/ /app/include/
COPY src/ /app/src/
COPY data/ /app/data/
COPY docs/ /app/docs/
COPY scripts/ /app/scripts/
