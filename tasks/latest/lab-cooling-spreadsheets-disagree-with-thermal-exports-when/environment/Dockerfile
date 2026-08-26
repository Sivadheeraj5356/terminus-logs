FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

ARG TERRAFORM_VERSION=1.9.8
ARG TERRAFORM_SHA256=186e0145f5e5f2eb97cbd785bc78f21bae4ef15119349f6ad4fa535b83b10df8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates=20230311+deb12u1 \
        curl=7.88.1-10+deb12u14 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-pil=9.4.0-1.1+deb12u1 \
        tmux \
        unzip=6.0-28 \
    && pip3 install --no-cache-dir --break-system-packages pytest==8.4.1 pytest-json-ctrf==0.3.5 \
    && rm -rf /var/lib/apt/lists/*

# Install pinned Terraform at build time (no network at agent/test runtime).
RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o /tmp/terraform.zip \
    && echo "${TERRAFORM_SHA256}  /tmp/terraform.zip" | sha256sum -c - \
    && unzip -q /tmp/terraform.zip -d /usr/local/bin \
    && rm /tmp/terraform.zip \
    && terraform version

COPY calibration_tf/ /usr/local/share/calibration_tf/
COPY . /app/

RUN cd /usr/local/share/calibration_tf && terraform init -input=false && terraform apply -auto-approve -input=false

RUN cd /app \
    && go mod download \
    && go build -o /app/bin/thermalcal ./cmd/thermalcal

ENV PATH="/usr/local/bin:/app/bin:${PATH}"
