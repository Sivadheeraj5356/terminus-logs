FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        less \
        nano \
        procps \
        python3-pytest \
        ripgrep \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 taskrunner

COPY task_file/ /app/task_file/
RUN rm -rf /app/task_file/output && mkdir -p /app/task_file/output

WORKDIR /app/task_file
CMD ["/bin/bash"]
