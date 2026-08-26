FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update && apt-get install -y --no-install-recommends asciinema=2.2.0-1 jq=1.6-2.1+deb12u2 python3=3.11.2-1+b1 python3-venv=3.11.2-1+b1 python-is-python3=3.11.2-1+deb12u1 tmux=3.3a-3 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier && \
    /opt/verifier/bin/pip install --require-hashes --no-deps -r /tmp/requirements.txt

ENV PATH="/opt/verifier/bin:${PATH}"

WORKDIR /app
COPY . /app/environment/
RUN mkdir -p /tmp/go-build /tmp/go-mod && \
    chmod a+w /app && \
    chmod -R a+w /app/environment /tmp/go-build /tmp/go-mod

ENV GOCACHE=/tmp/go-build
ENV GOMODCACHE=/tmp/go-mod
