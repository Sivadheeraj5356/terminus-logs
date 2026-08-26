# Edition 2 canonical base (check_sanctioned_base_images): public.ecr.aws node:22-bookworm-slim
FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        util-linux \
        ca-certificates \
        tmux \
        asciinema \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Verifier dependencies and local MLflow tracking server
RUN pip3 install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    mlflow==2.22.0 \
    requests==2.32.3 \
    pyyaml==6.0.2

COPY app/package.json app/package-lock.json ./
RUN npm ci --omit=dev

COPY app/ ./

RUN useradd --system --no-create-home --shell /usr/sbin/nologin taskworker \
    && chmod +x /app/scripts/start_mlflow.sh /app/worker.js \
    && mkdir -p /app/output /app/queue/done /app/mlflow_tracking /app/mlflow_artifacts \
    && chown -R taskworker:taskworker /app/output /app/queue /app/mlflow_tracking /app/mlflow_artifacts

ENV MLFLOW_TRACKING_URI=http://127.0.0.1:5000
ENV READINESS_CONTRACT_PATH=/app/config/readiness_contract.json
ENV READINESS_RULES_PATH=/app/config/readiness_rules.json
ENV MLFLOW_MANIFEST_PATH=/app/config/mlflow_manifest.json
ENV MODEL_WEIGHTS_PATH=/app/model/weights.json
ENV NODE_ENV=production
