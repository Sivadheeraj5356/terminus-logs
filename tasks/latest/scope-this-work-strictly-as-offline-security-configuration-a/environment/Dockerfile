FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

LABEL org.opencontainers.image.title="streamvault-offline-recovery"

ARG YQ_VERSION=v4.45.1
ARG YQ_SHA256=654d2943ca1d3be2024089eb4f270f4070f491a0610481d128509b2834870049

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        curl=7.88.1-10+deb12u15 \
        jq=1.6-2.1+deb12u2 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        sqlite3=3.40.1-2+deb12u2 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSLo /usr/local/bin/yq "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" \
    && echo "${YQ_SHA256}  /usr/local/bin/yq" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/yq \
    && yq --version | grep -F "${YQ_VERSION}"

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /workspace/streamvault
COPY streamvault/ /workspace/streamvault/

RUN mkdir -p /workspace/streamvault/data /workspace/streamvault/output \
    && sqlite3 /workspace/streamvault/data/fleet.db < /workspace/streamvault/fixtures/fleet.sql

CMD ["bash"]
