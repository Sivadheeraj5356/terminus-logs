FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3 \
      python3-pip \
      tmux \
      asciinema \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir pytest==8.4.1

WORKDIR /app

COPY src /app/src
COPY harness /app/harness
COPY docs /app/docs
COPY build.sh /app/build.sh
COPY smoke.sh /app/smoke.sh
COPY README.md /app/README.md

RUN bash build.sh
