# Canonical Terminal-Bench Java (Temurin JDK) base (docs/PLATFORM_AUTO_EVAL.md).
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.10.6-1~22.04.1 \
    python3-venv=3.10.6-1~22.04.1 \
    tmux=3.2a-4ubuntu0.2 \
    asciinema=2.1.0-1 \
    patch=2.7.6-7build2 \
    ca-certificates=20260601~22.04.1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5 \
      pytest-randomly==3.16.0
ENV PATH=/opt/verifier/bin:${PATH}

COPY README.md /app/README.md
COPY pom.xml /app/pom.xml
COPY docs /app/docs
COPY data /app/data
COPY fixtures /app/fixtures
COPY driver /app/driver
COPY common /app/common
COPY q7 /app/q7
COPY m4 /app/m4
COPY v9 /app/v9
COPY d1 /app/d1
COPY e3 /app/e3

RUN mkdir -p /app/output /app/work \
    && ln -sfn /app /app/environment \
    && find /app/driver -type f -name '*.sh' -exec chmod +x {} +
