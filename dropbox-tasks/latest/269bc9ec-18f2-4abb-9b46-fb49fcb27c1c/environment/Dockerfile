FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        curl \
        python-is-python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY pom.xml /app/pom.xml
RUN mvn -q -DskipTests dependency:go-offline

COPY config/ /app/config/
COPY docs/ /app/docs/
COPY input/ /app/input/
COPY src/ /app/src/
COPY --chmod=0755 scripts/ /app/scripts/

RUN mkdir -p /app/models /app/output \
    && mvn -q -DskipTests package dependency:copy-dependencies -DincludeScope=runtime

LABEL org.opencontainers.image.source="https://huggingface.co/ihoflaz/dibas-mobilenet-v3-large" \
      org.opencontainers.image.revision="42afed175c09a6b860fd7071283c3f9621ff4cd3" \
      org.opencontainers.image.version="1.0" \
      org.opencontainers.image.licenses="MIT"

CMD ["bash"]
