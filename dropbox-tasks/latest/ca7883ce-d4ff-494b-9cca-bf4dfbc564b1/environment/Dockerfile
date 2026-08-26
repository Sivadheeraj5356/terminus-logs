FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb AS wheelhouse

WORKDIR /tmp

RUN python -m pip download --dest /wheels \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

LABEL org.opencontainers.image.title="weather-hardened-audit-task" \
      org.opencontainers.image.description="R weather replay audit tool"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        tmux \
        r-base-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=wheelhouse /wheels /opt/verifier-wheels
RUN python -m pip install --no-index --find-links /opt/verifier-wheels \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY app/ /app/
