# Build Instructions

## Prerequisites

- Go 1.24 (provided in the Docker image)
- SQLite3 (provided in the Docker image)

## Build

From `/app`:

```bash
go build -o /app/app .
```

This produces the binary at `/app/app`.

## Run

```bash
/app/app <command> [args...]
```

See `/docs/API_SPEC.md` for the full command reference.

## Offline Build

The Docker image is built with `GOPROXY=off` after downloading dependencies during the image build step. All required modules are cached in the Go module cache inside the image.

## Module

Module name: `go-support-queue`  
Main dependency: `modernc.org/sqlite v1.34.5` (pure-Go SQLite, no CGo required)
