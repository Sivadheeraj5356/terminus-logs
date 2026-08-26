#!/bin/bash
set -euo pipefail

install -D -m 0644 /solution/main.rs /opt/linkseal/src/main.rs
rustc --edition=2021 -O /opt/linkseal/src/main.rs -o /opt/linkseal/bin/linkseal

