FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    APP_HOME=/app \
    HF_MIRROR_ROOT=/data/hf-mirror \
    HF_ASSET_LOCK=/app/config/hf-assets.lock.json \
    HF_TRANSCRIPT=/app/docs/release-council-transcript.md \
    HF_ROUTE_CONFIG=/app/config/terminology-routes.yml \
    GRADLE_USER_HOME=/app/.gradle-home \
    JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 \
    LC_ALL=C.UTF-8 \
    SPRING_PROFILES_ACTIVE=test

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash=5.1-6ubuntu1.1 \
        gawk=1:5.1.0-1ubuntu0.1 \
        coreutils=8.32-4.1ubuntu1.3 \
        findutils=4.8.0-1ubuntu3 \
        jq=1.6-2.1ubuntu3.2 \
        curl=7.81.0-1ubuntu1.25 \
        ca-certificates=20260601~22.04.1 \
        python3=3.10.6-1~22.04.1 \
        python3-pip=22.0.2+dfsg-1ubuntu0.7 \
        procps=2:3.3.17-6ubuntu2.1 \
        netcat-openbsd=1.218-4ubuntu1 \
        patch=2.7.6-7build2 \
        tmux=3.2a-4ubuntu0.2 \
        asciinema=2.1.0-1 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data /output /app/.gradle-home \
    && ln -sf /usr/bin/python3 /usr/bin/python

COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements-verifier.txt
RUN rm -f /tmp/requirements-verifier.txt

COPY app/ /app/
COPY data/ /data/

RUN chmod +x /app/gradlew \
    && find /app/kit -maxdepth 1 -name '*.sh' -exec chmod +x {} +

# Prefetch Gradle distribution and project dependencies at image build time.
RUN cd /app \
    && ./gradlew --no-daemon --stacktrace test bootJar \
    && ./gradlew --offline --no-daemon help
