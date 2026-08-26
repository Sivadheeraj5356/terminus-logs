FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e AS builder

WORKDIR /build
COPY app/pom.xml ./
RUN mvn -q -B dependency:go-offline
COPY app/ ./
RUN mvn -q -B package -DskipTests

FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-pip \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /usr/sbin/nologin agent

COPY --from=builder /usr/share/maven /usr/share/maven

COPY verifier-requirements.lock /tmp/verifier-requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps \
        -r /tmp/verifier-requirements.lock

WORKDIR /app

COPY --chown=agent:agent app/ /app/
COPY --chown=agent:agent docs/ /app/docs/
COPY --chown=agent:agent input/ /app/input/
COPY --chown=agent:agent bundled-fixtures/ /app/bundled-fixtures/

COPY --from=builder --chmod=755 /root/.m2 /opt/maven-cache
COPY --from=builder --chown=agent:agent /build/target/blendcert.jar /app/target/blendcert.jar

RUN mkdir -p /app/state /app/output \
    && chown agent:agent /app/state /app/output

ENV PATH="/usr/share/maven/bin:/opt/verifier-venv/bin:${PATH}"
