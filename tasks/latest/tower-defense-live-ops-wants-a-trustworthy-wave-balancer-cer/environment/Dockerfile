FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# verifier-bake-v2: offline pytest in /opt/verifier
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3=3.12.3-0ubuntu2.1 \
        python3-venv=3.12.3-0ubuntu2.1 \
        tmux=3.4-1ubuntu0.1 \
        asciinema=2.4.0-1 \
        patch=2.7.6-7build3 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-randomly==3.16.0
RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest \
    && ln -sf /opt/verifier/bin/python /usr/local/bin/python
ENV PATH=/opt/verifier/bin:${PATH}

COPY . /app/environment/

RUN chmod +x /app/environment/drv/run_td.sh /app/environment/drv/lib_boot.sh
