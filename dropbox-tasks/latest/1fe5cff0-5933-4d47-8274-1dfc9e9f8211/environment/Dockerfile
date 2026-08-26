FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

LABEL org.opencontainers.image.title="indigo-palisade-mediator"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

ENV CLOJURE_VERSION=1.12.5.1654

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        curl \
        make \
        python3 \
        python3-pip \
        rlwrap \
        tmux \
    && curl -fsSLO "https://download.clojure.org/install/linux-install-${CLOJURE_VERSION}.sh" \
    && echo "28f81b0833c0a072f4370ae0eb1e4c5a4f9f4a34035cd7607ea9f253a8b06da1 *linux-install-${CLOJURE_VERSION}.sh" | sha256sum -c - \
    && chmod +x "linux-install-${CLOJURE_VERSION}.sh" \
    && "./linux-install-${CLOJURE_VERSION}.sh" \
    && rm "linux-install-${CLOJURE_VERSION}.sh" \
    && clojure -e "(clojure-version)" \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir \
        --ignore-installed --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

COPY app/deps.edn app/Makefile /app/
COPY app/src /app/src
RUN cd /app && clojure -Spath > /dev/null

COPY app/ /app/

RUN sed -i 's/\r$//' /app/bin/* \
    && chmod +x /app/bin/mediate-deps \
    && make -C /app clean all
