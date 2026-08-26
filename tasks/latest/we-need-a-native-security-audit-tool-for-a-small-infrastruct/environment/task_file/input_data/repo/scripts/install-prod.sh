#!/bin/sh
set -eu

curl -fsSL https://deploy.example.internal/bootstrap.sh | sudo bash
echo "deployment bootstrap complete"
