# Canonical Temurin JDK image for the Memory Vault dungeon adventure.
# Verifier Python stack is installed beside it for offline play scoring.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
                asciinema=2.1.0-1 \
                ca-certificates=20260601~22.04.1 \
                patch=2.7.6-7build2 \
                python3=3.10.6-1~22.04.1 \
                python3-pip=22.0.2+dfsg-1ubuntu0.7 \
                python3-venv=3.10.6-1~22.04.1 \
                tmux=3.2a-4ubuntu0.2 \
                && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

RUN ln -sf /usr/bin/python3 /usr/bin/python

ENV PATH="/opt/verifier/bin:${PATH}"

RUN mkdir -p /app/output /app/environment
COPY . /app/environment
RUN chmod +x /app/environment/campaign/play.sh
