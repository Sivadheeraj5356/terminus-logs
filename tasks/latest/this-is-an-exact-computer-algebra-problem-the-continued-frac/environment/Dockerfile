FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

ARG TARGETARCH

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    JULIA_DEPOT_PATH=/opt/julia-depot \
    DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/julia/bin:$PATH

WORKDIR /app

RUN apt-get -o Acquire::Retries=5 update \
    && apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
         asciinema bash ca-certificates coreutils curl libgomp1 procps python3 python3-pip tmux \
    && rm -rf /var/lib/apt/lists/*

RUN case "$TARGETARCH" in \
         amd64) julia_path=x64; julia_arch=x86_64; julia_sha=bbabf3bef19421a9dbd24a767d807606ab85e444323b5a1c73ffe293fa3d079a ;; \
         arm64) julia_path=aarch64; julia_arch=aarch64; julia_sha=029b93b857bd0ffd627f9a8580d3bbaa63daf008d7b7aed02fbceb8fd57c4899 ;; \
         *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL --retry 5 --retry-delay 2 --retry-connrefused "https://julialang-s3.julialang.org/bin/linux/${julia_path}/1.12/julia-1.12.6-linux-${julia_arch}.tar.gz" -o /tmp/julia.tar.gz \
    && echo "${julia_sha}  /tmp/julia.tar.gz" | sha256sum -c - \
    && mkdir -p /opt/julia && tar -xzf /tmp/julia.tar.gz -C /opt/julia --strip-components=1 && rm /tmp/julia.tar.gz

RUN python3 -m pip install --break-system-packages --no-cache-dir --retries 5 --timeout 60 pytest==8.4.1 pytest-json-ctrf==0.3.5

COPY src/ /app/src/
