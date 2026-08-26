#!/bin/bash
set -e
cd /app
rm -rf out
mkdir -p out
javac -d out src/*.java harness/*.java
