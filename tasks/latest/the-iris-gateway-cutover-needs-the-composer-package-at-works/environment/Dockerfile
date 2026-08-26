# Canonical sanctioned base (Edition 2 table): debian:bookworm-slim @ digest below.
# There is no PHP image in the canonical ECR language table; install PHP CLI and
# extensions with apt on this base (same pattern as Perl-on-Debian tasks).
# Vendor PHP deps ship under iris-provenance/vendor so the image build does not
# fetch Composer packages from the network.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

RUN apt-get update && apt-get install -y --no-install-recommends \
    php-cli \
    php-sqlite3 \
    php-xml \
    php-mbstring \
    php-zip \
    unzip \
    ca-certificates \
    python3 \
    python3-pip \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

WORKDIR /workspace
COPY workspace/ /workspace/

RUN test -x /workspace/iris-provenance/vendor/bin/phinx \
    && chmod +x /workspace/iris-provenance/bin/iris-prov \
        /workspace/iris-provenance/scripts/verify-provenance.sh \
        /workspace/iris-provenance/vendor/bin/phinx \
    && mkdir -p /workspace/state /workspace/output

USER root
