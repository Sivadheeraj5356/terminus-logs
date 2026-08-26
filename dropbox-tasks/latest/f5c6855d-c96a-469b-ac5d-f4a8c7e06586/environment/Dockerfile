FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN printf 'Acquire::Retries "5";\n' > /etc/apt/apt.conf.d/80-retries \
    && apt-get update && apt-get install -y --no-install-recommends \
      r-base-core tmux asciinema python3-pytest python3-scipy \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --chmod=0755 run.sh /app/run.sh
COPY estimate.R /app/estimate.R
COPY docs/ /app/docs/
COPY data/ /app/data/
