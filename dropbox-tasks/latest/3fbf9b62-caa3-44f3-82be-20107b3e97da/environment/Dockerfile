FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive

ENV GO_VERSION=1.22.5
ARG GO_SHA256=904b924d435eaea086515bc63235b192ea441bd8c9b198c507e85009e6e4c7f0

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        python3 \
        python3-pip \
        build-essential \
        pkg-config \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o /tmp/go.tgz \
    && echo "${GO_SHA256}  /tmp/go.tgz" | sha256sum -c - \
    && tar -C /usr/local -xzf /tmp/go.tgz \
    && rm /tmp/go.tgz \
    && pip3 install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.lock

ENV PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH}"

WORKDIR /app

COPY app/ /app/

RUN chmod +x scripts/build.sh \
    && bash scripts/build.sh

CMD ["bash"]
