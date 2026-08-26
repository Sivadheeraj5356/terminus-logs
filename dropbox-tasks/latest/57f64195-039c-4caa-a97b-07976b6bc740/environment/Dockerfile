FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

# Runtime rebuild of the TOF mass-axis numerical evaluator is required by the metrology contract.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        libcurl4-openssl-dev \
        libjansson-dev \
        libssl-dev \
        make \
        pkg-config \
        python3 \
        python3-pip \
        python-is-python3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app
COPY toflab/ /app/

RUN mkdir -p /app/reports /app/build /app/bin \
    && chmod 0755 /app/scripts/start-instrument.sh /app/bin/tofmass \
    && make -C /app
