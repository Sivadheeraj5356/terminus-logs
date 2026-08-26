# Canonical Java/Maven runtime (edition_2 static checks).
FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
    asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock

ENV PATH="/opt/venv/bin:${PATH}"

COPY app/ /app/

RUN mvn -q -B dependency:resolve-plugins dependency:go-offline test-compile \
    && mvn -q -B test \
    && mvn -q -B install -DskipTests \
    && mvn -q -B -o test \
    && mvn -q -B -pl coinsurance-batch org.codehaus.mojo:exec-maven-plugin:3.1.1:help

RUN rm -rf /app/output
