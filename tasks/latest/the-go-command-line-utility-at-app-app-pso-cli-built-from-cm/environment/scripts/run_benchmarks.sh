#!/bin/bash
echo "Running benchmarks..."
go test -bench . ./internal/pso
