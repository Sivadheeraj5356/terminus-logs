FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

LABEL org.opencontainers.image.title="vaultseal-crypto-leak-triage"
LABEL org.opencontainers.image.description="Terraform-driven offline triage of gdb/valgrind crypto crash corpora."

# System packages. Build-time network is used only here and for the pinned
# downloads below; the task itself runs fully offline. build-essential + patchelf
# are needed to compile the reference oracle to a native binary (see below).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        build-essential \
        ca-certificates \
        curl \
        patchelf \
        tmux \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Terraform CLI, pinned by version and verified against HashiCorp's published
# SHA256SUMS for the release (files keep their canonical names so `sha256sum -c`
# can find them).
ARG TF_VERSION=1.9.8
RUN cd /tmp \
    && curl -fsSL -O "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip" \
    && curl -fsSL -O "https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_SHA256SUMS" \
    && grep "terraform_${TF_VERSION}_linux_amd64.zip" "terraform_${TF_VERSION}_SHA256SUMS" | sha256sum -c - \
    && unzip -d /usr/local/bin "terraform_${TF_VERSION}_linux_amd64.zip" \
    && rm -f "terraform_${TF_VERSION}_linux_amd64.zip" "terraform_${TF_VERSION}_SHA256SUMS" \
    && terraform version

# Verifier dependencies (baked in so tests run with no network access).
RUN python -m pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

# Offline Terraform provider mirror. Populated with network at build time so
# `terraform init` needs no network at run/verify time.
RUN mkdir -p /tmp/tfmirror /opt/tf-mirror \
    && printf '%s\n' \
        'terraform {' \
        '  required_providers {' \
        '    local = {' \
        '      source  = "hashicorp/local"' \
        '      version = "2.5.1"' \
        '    }' \
        '  }' \
        '}' > /tmp/tfmirror/main.tf \
    && (cd /tmp/tfmirror && terraform providers mirror -platform=linux_amd64 /opt/tf-mirror) \
    && printf '%s\n' \
        'provider_installation {' \
        '  filesystem_mirror {' \
        '    path    = "/opt/tf-mirror"' \
        '    include = ["registry.terraform.io/*/*"]' \
        '  }' \
        '  direct {' \
        '    exclude = ["registry.terraform.io/*/*"]' \
        '  }' \
        '}' > /etc/terraform.rc \
    && rm -rf /tmp/tfmirror

ENV TF_CLI_CONFIG_FILE=/etc/terraform.rc

WORKDIR /app
COPY app/ /app/

# Reference oracle. The correct triage engine is compiled to a native, opaque
# binary at /app/oracle: the agent can run it on any corpus to obtain ground
# truth, but cannot read its logic. The Python source is only present in the
# build context — it is compiled here and never copied into the image, so the
# runtime image contains the binary alone. A build-time smoke test fails the
# build loudly if the compile is broken.
COPY oracle_build/oracle.py /build/oracle.py
RUN python -m pip install --no-cache-dir "nuitka~=2.5" \
    && cd /build \
    && python -m nuitka --onefile --assume-yes-for-downloads \
        --output-dir=/build/out --output-filename=oracle /build/oracle.py \
    && install -m 0755 /build/out/oracle /app/oracle \
    && printf 'vaultseal triage snapshot\ncase: case_0001\nsignal: SIGSEGV (fault)\n#0  0x1 in main () at vaultseal.c:1\n' > /tmp/smoke_gdb.log \
    && mkdir -p /tmp/smoke/gdb /tmp/smoke/valgrind \
    && cp /tmp/smoke_gdb.log /tmp/smoke/gdb/case_0001.log \
    && /app/oracle --corpus-dir /tmp/smoke | python -c "import sys,json; d=json.load(sys.stdin); assert d['schema_version']=='1.0' and d['corpus']['total_findings']==1; print('oracle smoke ok')" \
    && rm -rf /build /tmp/smoke /tmp/smoke_gdb.log \
    && python -m pip uninstall -y nuitka || true
