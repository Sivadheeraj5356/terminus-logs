FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        cmake \
        make \
        imagemagick \
        libssl-dev \
        python3 \
        python3-pip \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY CMakeLists.txt /app/CMakeLists.txt
COPY src/ /app/src/
COPY spec/ /app/spec/
COPY assets/ /app/assets/

RUN mkdir -p /app/out /app/build
