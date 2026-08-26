FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        bash python3 python3-pip tmux util-linux asciinema \
 && rm -rf /var/lib/apt/lists/*

COPY wheels/ /opt/wheels/
RUN pip3 install --no-cache-dir \
    --no-index --find-links /opt/wheels/ \
    pytest==8.2.2 pytest-json-ctrf==0.3.5 exceptiongroup tomli

COPY app/ /app/

RUN javac -d /tmp/sawsplitclasses /app/Main.java /app/Sawmill.java
