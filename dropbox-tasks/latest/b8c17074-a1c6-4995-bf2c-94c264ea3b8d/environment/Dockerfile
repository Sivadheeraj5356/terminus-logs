FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    make \
    python3 \
    python3-pip \
  && rm -rf /var/lib/apt/lists/* \
  && python3 -m pip install --break-system-packages --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

WORKDIR /app
COPY data /app/data
COPY work /app/work
COPY docs /app/docs
COPY src /app/src
COPY Makefile /app/Makefile
RUN ln -s /app /app/environment
ENV PATH="/app/bin:${PATH}"
