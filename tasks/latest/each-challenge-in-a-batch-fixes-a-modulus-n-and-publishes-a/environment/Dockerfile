FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

ARG TARGETARCH

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/julia/bin:/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         asciinema \
         bash \
         ca-certificates \
         coreutils \
         curl \
         libgomp1 \
         procps \
         python3 \
         python3-pip \
         python3-venv \
         tmux \
    && rm -rf /var/lib/apt/lists/*

RUN case "$TARGETARCH" in \
         amd64) julia_path=x64; julia_arch=x86_64; julia_sha=bbabf3bef19421a9dbd24a767d807606ab85e444323b5a1c73ffe293fa3d079a ;; \
         arm64) julia_path=aarch64; julia_arch=aarch64; julia_sha=029b93b857bd0ffd627f9a8580d3bbaa63daf008d7b7aed02fbceb8fd57c4899 ;; \
         *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://julialang-s3.julialang.org/bin/linux/${julia_path}/1.12/julia-1.12.6-linux-${julia_arch}.tar.gz" -o /tmp/julia.tar.gz \
    && echo "${julia_sha}  /tmp/julia.tar.gz" | sha256sum -c - \
    && mkdir -p /opt/julia \
    && tar -xzf /tmp/julia.tar.gz -C /opt/julia --strip-components=1 \
    && rm /tmp/julia.tar.gz

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY attack /app/environment/attack
COPY docs /app/environment/docs
COPY samples /app/environment/samples
