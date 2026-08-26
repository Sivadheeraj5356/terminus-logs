FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        tmux \
        asciinema \
        libgl1 \
        libegl1 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libfontconfig1 \
        libfreetype6 \
        libgpg-error0 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L -o /tmp/minizinc.tgz \
        https://github.com/MiniZinc/MiniZincIDE/releases/download/2.9.7/MiniZincIDE-2.9.7-bundle-linux-x86_64.tgz \
    && echo "7e78d3a1d6feec2f5b6a43628632decb6995755ade92ff4e51a2188c54ca6399  /tmp/minizinc.tgz" | sha256sum -c - \
    && mkdir -p /opt/minizinc \
    && tar -xzf /tmp/minizinc.tgz -C /opt/minizinc --strip-components=1 \
    && rm /tmp/minizinc.tgz \
    && printf '#!/bin/sh\nexport LD_LIBRARY_PATH="/opt/minizinc/lib:${LD_LIBRARY_PATH}"\nexec /opt/minizinc/bin/minizinc "$@"\n' > /usr/local/bin/minizinc \
    && chmod 0755 /usr/local/bin/minizinc

ENV PATH="/opt/minizinc/bin:${PATH}"
ENV LD_LIBRARY_PATH="/opt/minizinc/lib:${LD_LIBRARY_PATH}"

RUN pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

WORKDIR /app

COPY instance.dzn /app/instance.dzn
COPY docs/ /app/docs/
COPY samples/ /app/samples/
COPY consumables/ /app/consumables/
COPY facilities/ /app/facilities/
COPY run_model.sh /app/run_model.sh
COPY model.mzn /app/model.mzn
