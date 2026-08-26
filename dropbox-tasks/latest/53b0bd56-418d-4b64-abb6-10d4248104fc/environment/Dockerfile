FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c AS instrument

WORKDIR /src
COPY instrument/ /src/
RUN make && strip --strip-all bench

FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-venv \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY bench/ /app/bench/
COPY --from=instrument /src/bench /app/bench/bench
COPY calibration/ /app/calibration/
COPY assay/ /app/assay/
COPY archive/ /app/archive/

RUN mkdir -p /app/bin
