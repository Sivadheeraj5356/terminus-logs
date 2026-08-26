FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
ARG CACHEBUST=cicache-runner-scope-1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        acl \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
# Six downstream job accounts (the cache readers), each with its own private primary group of the same
# name. A job gains read on an artifact cache only through a runner-group tier it already sits in; the
# agent never edits job tier membership, only decides which tier each cache is delegated through.
RUN groupadd job1 \
    && groupadd job2 \
    && groupadd job3 \
    && groupadd job4 \
    && groupadd job5 \
    && groupadd job6 \
    && useradd -M -N -g job1 job1 \
    && useradd -M -N -g job2 job2 \
    && useradd -M -N -g job3 job3 \
    && useradd -M -N -g job4 job4 \
    && useradd -M -N -g job5 job5 \
    && useradd -M -N -g job6 job6
# Four runner accounts (the cache writers), each with its own private primary group of the same name. A
# runner writes fresh build artifacts into the caches it owns; a downstream job never writes.
RUN groupadd runA \
    && groupadd runB \
    && groupadd runC \
    && groupadd runD \
    && useradd -M -N -g runA runA \
    && useradd -M -N -g runB runB \
    && useradd -M -N -g runC runC \
    && useradd -M -N -g runD runD
# Four runner-group tiers with fixed, seeded rosters (charter section 2). These rosters are given; the
# agent does not add or remove members. A cache delegated through a tier grants read to every member of
# that roster, so a cache may ride a tier only when the roster covers all of the cache's required jobs
# and contains none of its forbidden jobs.
RUN groupadd rgW && gpasswd -M job1,job3,job6 rgW \
    && groupadd rgX && gpasswd -M job2,job3,job6 rgX \
    && groupadd rgY && gpasswd -M job1,job4,job6 rgY \
    && groupadd rgZ && gpasswd -M job2,job5,job6 rgZ
# Eight artifact caches ship bare: each is an empty directory owned root:root 0755 with no ACL, so no
# runner can drop into it and no job can read it. The agent brings each cache to its settled delegation
# and sets the drop rules that every later artifact file inherits.
RUN mkdir -p /srv/ci-cache \
    && mkdir -p /srv/ci-cache/lint /srv/ci-cache/api /srv/ci-cache/web /srv/ci-cache/infra \
                /srv/ci-cache/data /srv/ci-cache/mobile /srv/ci-cache/ml /srv/ci-cache/docs \
    && chown root:root /srv /srv/ci-cache /srv/ci-cache/* \
    && chmod 0755 /srv /srv/ci-cache /srv/ci-cache/*
COPY workspace/ /app/
