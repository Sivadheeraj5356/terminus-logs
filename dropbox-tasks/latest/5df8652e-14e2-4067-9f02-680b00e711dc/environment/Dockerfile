FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

COPY requirements.lock /tmp/requirements.lock
COPY vendor /tmp/vendor

ENV DEBIAN_FRONTEND=noninteractive

RUN set -eu; \
    arch="$(dpkg --print-architecture)"; \
    test "$arch" = "amd64"; \
    debs="/tmp/vendor/apt/amd64"; \
    dpkg -i "$debs"/libc6_*.deb "$debs"/libc-bin_*.deb "$debs"/libexpat1_*.deb "$debs"/libpython3.11-minimal_*.deb >/dev/null; \
    dpkg -i "$debs"/python3.11-minimal_*.deb >/dev/null; \
    dpkg -i "$debs"/python3-minimal_*.deb >/dev/null; \
    dpkg -i "$debs"/*.deb >/dev/null || true; \
    dpkg --configure -a >/dev/null; \
    test -z "$(dpkg --audit)"; \
    rm -rf /tmp/vendor/apt

RUN PIP_NO_INDEX=1 python -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --no-index \
    --find-links=/tmp/vendor/wheels \
    --require-hashes \
    --no-deps \
    -r /tmp/requirements.lock \
    && rm -rf /tmp/vendor /tmp/requirements.lock

WORKDIR /app

COPY app /app
