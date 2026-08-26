FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

ENV PATH=/opt/verifier/bin:${PATH}
ENV PYTHONPATH=/app

COPY shed_weave /app/shed_weave
COPY heddle_bind /app/heddle_bind
COPY atelier_chain /app/atelier_chain
COPY chroma_record /app/chroma_record
COPY relay_cordage /app/relay_cordage
COPY loom_shed /app/loom_shed
COPY recital_stub /app/recital_stub
COPY tint_audit /app/tint_audit
COPY data /app/data
COPY config /app/config
COPY docs /app/docs
COPY fixtures /app/fixtures

CMD ["python3", "-c", "print('historic organ weaver registry ready')"]
