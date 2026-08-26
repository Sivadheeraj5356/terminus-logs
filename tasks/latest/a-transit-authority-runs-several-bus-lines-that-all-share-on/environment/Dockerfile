FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        libstdc++6 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY vendor/minizinc-2.9.7-chuffed-linux-x86_64.tar.gz /tmp/minizinc.tar.gz
RUN echo "1abc697f71895231053cccac70d1c04a307dd64ef32820b40813d67fa2395fb6  /tmp/minizinc.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/minizinc.tar.gz -C /usr/local \
    && rm /tmp/minizinc.tar.gz

RUN minizinc --solver chuffed --version

RUN pip install --no-cache-dir pytest==8.2.0

WORKDIR /app

COPY instance.dzn /app/instance.dzn
COPY docs/ /app/docs/
COPY run_model.sh /app/run_model.sh
COPY model.mzn /app/model.mzn
