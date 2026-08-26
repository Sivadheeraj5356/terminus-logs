FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        patch=2.7.6-7 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.txt

COPY app/pyproject.toml /app/pyproject.toml
COPY app/cfaxis /app/cfaxis
COPY app/docs /app/docs
COPY app/tools /app/tools
COPY app/data /app/data
COPY app/RUNBOOK.md /app/RUNBOOK.md
COPY app/README.md /app/README.md

RUN pip3 install --no-cache-dir --break-system-packages --no-deps -e .

RUN python3 -c "import cfaxis" \
    && climconvert --help >/dev/null

RUN ln -sfn /app/data /data \
    && mkdir -p /output /var/lib/climconvert/cache /var/lib/climconvert/climate_axis \
    && python3 /app/tools/build_climate_axis_fixture.py \
    && mkdir -p /app/bin \
    && ln -sf /usr/local/bin/climconvert /app/bin/climconvert \
    && /app/bin/climconvert --help >/dev/null \
    && chmod a+rwX /output /var/lib/climconvert/cache /var/lib/climconvert/climate_axis /app/data/segments

ENV TZ=UTC
ENV LC_ALL=C.UTF-8
ENV PATH="/app/bin:/usr/local/bin:${PATH}"
