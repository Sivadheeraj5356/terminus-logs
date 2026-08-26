FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update && apt-get install -y --no-install-recommends \
      tmux asciinema python3 python3-pip python3-pytest \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Makefile /app/Makefile
COPY src /app/src
