FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d
ENV DEBIAN_FRONTEND=noninteractive
ARG DART_VERSION=3.8.1-1
WORKDIR /app
COPY requirements.lock /tmp/requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends \
        apt-transport-https \
        asciinema \
        ca-certificates \
        coreutils \
        curl \
        gnupg \
        python3 \
        python3-pip \
        tmux \
        zip \
    && curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub \
        | gpg --dearmor -o /usr/share/keyrings/dart.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/dart.gpg] https://storage.googleapis.com/download.dartlang.org/linux/debian stable main" \
        > /etc/apt/sources.list.d/dart_stable.list \
    && apt-get update && apt-get install -y --no-install-recommends dart=${DART_VERSION} \
    && apt-mark hold dart \
    && pip3 install --no-cache-dir --break-system-packages --ignore-installed --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements.lock
RUN mkdir -p /app/src /app/output /app/data /app/docs
COPY data/workbook.json /app/data/workbook.json
COPY docs/SPEC.md /app/docs/SPEC.md
CMD ["bash"]
