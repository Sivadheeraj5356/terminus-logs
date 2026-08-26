FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pytest \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY build.sh /app/build.sh
COPY README.md /app/README.md
COPY src/ /app/src/
COPY docs/ /app/docs/
COPY programs/ /app/programs/

RUN chmod +x /app/build.sh && /app/build.sh
