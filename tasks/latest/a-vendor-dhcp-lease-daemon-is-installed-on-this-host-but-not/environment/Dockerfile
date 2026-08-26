# Canonical Docker Hub Python 3.13 slim base: pytest is the verifier's test
# runner and pip installs the test dependencies. The DHCP lease daemon is a
# pre-compiled OCaml component built from source at image-build time (Debian
# bookworm packages the OCaml toolchain via apt); the agent's deliverable is
# pure bash/SQL host administration.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

COPY requirements.lock /tmp/requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends \
        ocaml \
        ocaml-findlib \
        sqlite3 \
        jq \
        passwd \
        adduser \
        cron \
        logrotate \
        procps \
        tmux \
        asciinema \
        openssl \
        sudo \
    && pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/ /app/

# Compile and stage the vendor-provided lease daemon under /opt/dhcpd. The host
# itself is left unconfigured on purpose: no service account, no state
# directory, no administrative front-end, and no scheduled maintenance exist
# yet. Bringing the appliance into service is the administrator's job.
RUN chmod +x /app/build.sh && bash /app/build.sh

CMD ["bash"]
