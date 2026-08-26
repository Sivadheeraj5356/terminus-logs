FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        attr=1:2.5.1-4 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        patch=2.7.6-7 \
        jq=1.6-2.1+deb12u2 \
        ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app/ /app/

RUN mkdir -p /app/bin /output /logs/verifier /logs/agent \
    && chmod 0777 /output \
    && cp /app/scripts/restore-bundle /app/bin/restore-bundle \
    && chmod 0755 /app/bin/restore-bundle

ENV PYTHONPATH=/app/src:/app
ENV PYTHONUNBUFFERED=1
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

WORKDIR /app

CMD ["sleep", "infinity"]
