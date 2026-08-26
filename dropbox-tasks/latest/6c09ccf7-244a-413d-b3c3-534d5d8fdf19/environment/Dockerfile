# debian:bookworm-slim canonical base: this task administers OS accounts,
# groups, a county registry's seal and register, and file custody, which need
# the distribution's own account and coreutils tooling; the registrar's seal is
# cut at container start with the distribution's own openssl.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV BUILD_MARKER=20260721T0200-aldreth-deeds-registry-host-v1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        login \
        passwd \
        procps \
        openssl \
        openssh-client \
        python3 python3-pip \
        tmux asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /opt/registry/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages -r /opt/registry/requirements.lock

COPY opt/registry /opt/registry
COPY etc/registry /etc/registry
COPY entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

WORKDIR /srv/registry

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
