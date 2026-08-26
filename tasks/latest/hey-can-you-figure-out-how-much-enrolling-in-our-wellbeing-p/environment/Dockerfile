FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        ca-certificates \
        make \
        r-base-core \
        r-cran-jsonlite \
    && rm -rf /var/lib/apt/lists/*


RUN pip3 install --no-cache-dir --break-system-packages pytest==8.2.0 numpy==2.1.3

WORKDIR /app

COPY data/ /app/data/
COPY docs/ /app/docs/
COPY R/ /app/R/
COPY DESCRIPTION /app/DESCRIPTION
