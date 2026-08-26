# The agent solves this task in R, but the sanctioned base-image list has no R
# image. We use the sanctioned Python image because the Harbor verifier runs on
# pytest (Python), and install R plus its packages from apt below.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN for attempt in 1 2 3 4 5; do \
        apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        tmux \
        asciinema \
        r-base-core \
        r-cran-readr \
        r-cran-dplyr \
        r-cran-tidyr \
        r-cran-jsonlite \
        r-cran-stringr \
        r-cran-lubridate && break; \
        echo "apt retry $attempt"; apt-get clean; sleep 20; \
    done && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest==8.4.1

COPY data/ /app/data/
COPY docs/ /app/docs/
COPY R/ /app/R/
COPY DESCRIPTION /app/DESCRIPTION
COPY analysis.R /app/analysis.R
