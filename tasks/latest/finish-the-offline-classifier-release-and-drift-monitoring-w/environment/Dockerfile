# Prefect 2.20.25 does not support Python 3.13. Use the canonical Debian
# runtime so Bookworm's Python 3.11 can install and run the locked workflow.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

WORKDIR /app

COPY app/README.md /app/README.md
COPY app/docs/ /app/docs/
COPY app/config/ /app/config/
COPY app/scripts/ /app/scripts/
COPY app/p/ /app/p/
COPY app/django_api/ /app/django_api/

RUN chmod +x /app/p/wf \
    && find /app/p/lib -name '*.sh' -exec chmod +x {} + \
    && python /app/scripts/create_training_parquet.py \
    && cd /app/django_api \
    && python manage.py migrate --noinput \
    && python manage.py seed_records

ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=drift_api.settings
ENV PREFECT_TEST_MODE=1
ENV PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=120
ENV PREFECT_LOGGING_TO_API_ENABLED=false
ENV PREFECT_SERVER_ANALYTICS_ENABLED=false
ENV PREFECT_API_SERVICES_SCHEDULER_ENABLED=false
ENV PREFECT_API_SERVICES_LATE_RUNS_ENABLED=false
ENV PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED=false
ENV PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED=false
ENV PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED=false
ENV PREFECT_API_SERVICES_FOREMAN_ENABLED=false
ENV PREFECT_API_SERVICES_EVENT_LOGGER_ENABLED=false
ENV PREFECT_API_SERVICES_TRIGGERS_ENABLED=false
ENV PREFECT_API_SERVICES_EVENT_PERSISTER_ENABLED=false
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1

CMD ["sleep", "infinity"]
