#!/bin/bash
set -euo pipefail

cd /opt/bottleplan/app
cp /solution/fixed/go.mod /opt/bottleplan/app/go.mod
cp /solution/fixed/main.go /opt/bottleplan/app/cmd/bottleplan/main.go
/usr/local/go/bin/go build -o /opt/bottleplan/app/bin/bottleplan ./cmd/bottleplan
