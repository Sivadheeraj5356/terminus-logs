FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        cmake=3.25.1-1 \
        g++=4:12.2.0-3 \
        make=4.3-4.1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        ncurses-term=6.4-4 \
        util-linux=2.38.1-5+deb12u3 \
        passwd=1:4.13+dfsg1-1+deb12u2 \
    && groupadd --gid 10001 lockctl \
    && useradd --uid 10001 --gid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin --no-create-home lockctl \
    && mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY CMakeLists.txt /app/environment/CMakeLists.txt
COPY include/ /app/environment/include/
COPY src/ /app/environment/src/
COPY docs/ /app/environment/docs/
COPY schemas/ /app/environment/schemas/
COPY data/ /app/environment/data/
COPY runtime/tmux.conf /etc/tmux.conf

RUN mkdir -p /app/output /app/environment/output \
    && chmod 0777 /app/output /app/environment/output
