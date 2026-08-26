FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends --no-upgrade \
      binutils \
      ca-certificates \
      python3 \
      python3-pip \
      python3-venv \
      asciinema \
      tmux \
 && rm -rf /var/lib/apt/lists/*

COPY unitgraph_wheel_vaults /tmp/unitgraph_wheel_vaults
COPY unitgraph_pytest_anchors.lock /tmp/unitgraph_pytest_anchors.lock
RUN python3 -m venv /opt/unitgraph_verifier_venv \
 && /opt/unitgraph_verifier_venv/bin/python3 -m pip install \
      --no-index --no-deps --require-hashes \
      --find-links /tmp/unitgraph_wheel_vaults \
      -r /tmp/unitgraph_pytest_anchors.lock \
 && rm -rf /tmp/unitgraph_wheel_vaults /tmp/unitgraph_pytest_anchors.lock

COPY boot_transaction_switchboard/forge_boot_reconciler.sh /opt/boot_transaction_switchboard/forge_boot_reconciler.sh
COPY boot_transaction_switchboard/sealed_rule_capsule_manifest.tsv /opt/boot_transaction_switchboard/sealed_rule_capsule_manifest.tsv
COPY boot_transaction_switchboard/systemd_boot_contracts /opt/boot_transaction_switchboard/systemd_boot_contracts
COPY boot_transaction_switchboard/rust_unitgraph_cells /opt/boot_transaction_switchboard/rust_unitgraph_cells

RUN bash /opt/boot_transaction_switchboard/forge_boot_reconciler.sh /opt/boot_transaction_switchboard \
 && test -x /app/boot_recovery_console/reconcile_boot_graph.sh \
 && test -x /app/rust_unitgraph_cells/reconcile_boot_graph

WORKDIR /app
