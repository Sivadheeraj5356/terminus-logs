# Builder uses the sanctioned Maven+Temurin ECR image. The final stage copies
# that JDK, Maven toolchain, and the populated ~/.m2 cache so offline
# `mvn -o package` works under allow_internet=false.
FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e AS java_builder
WORKDIR /build
COPY pom.xml /build/pom.xml
COPY src /build/src
RUN mvn -q -f /build/pom.xml package \
    && mvn -q -f /build/pom.xml dependency:go-offline

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV JAVA_HOME=/opt/java/openjdk
ENV MAVEN_HOME=/usr/share/maven
ENV PATH="/app/bin:/usr/share/maven/bin:/opt/java/openjdk/bin:${PATH}"

COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        r-base-core=4.2.2.20221110-2 \
        r-cran-jsonlite=1.8.4+dfsg-1 \
        strace=6.1-0.1 \
        tmux=3.3a-3 \
        util-linux=2.38.1-5+deb12u3 \
    && pip3 install --no-cache-dir -r /tmp/requirements-verifier.txt \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements-verifier.txt

COPY --from=java_builder /opt/java/openjdk /opt/java/openjdk
COPY --from=java_builder /usr/share/maven /usr/share/maven
COPY --from=java_builder /root/.m2 /root/.m2

WORKDIR /app
COPY pom.xml /app/pom.xml
COPY bin /app/bin
COPY scripts /app/scripts
COPY r /app/r
COPY fixtures /app/fixtures
COPY config /app/config
COPY schema /app/schema
COPY var /app/var
COPY src /app/src
COPY --from=java_builder /build/target/fold-assembler-1.0.0.jar /app/target/fold-assembler-1.0.0.jar

RUN chmod +x /app/bin/foldctl /app/scripts/stage_cohort.sh /app/r/fold_balance.R \
    && mkdir -p /app/var/fold_work /app/target \
    && chmod -R a+rX /root/.m2 /usr/share/maven /opt/java/openjdk /app \
    && chmod 0777 /app/var /app/var/fold_work
