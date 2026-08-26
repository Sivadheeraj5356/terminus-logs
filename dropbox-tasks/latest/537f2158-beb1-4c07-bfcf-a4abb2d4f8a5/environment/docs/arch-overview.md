# FinchRender Architecture Overview

## System Components

```
  ┌─────────────────┐
  │  Artist Network │
  │  10.200.0.0/16  │
  └────────┬────────┘
           │ HTTPS :443
  ┌────────▼────────────────────────────────────┐
  │         Coordinator Host (10.100.1.10)       │
  │                                              │
  │  ┌──────────────┐    ┌──────────────────┐   │
  │  │   Nginx TLS  │───►│ Gateway Service  │   │
  │  │  Reverse     │    │ finchrender-gw   │   │
  │  │  Proxy       │    │ :8080 (loopback) │   │
  │  └──────────────┘    └────────┬─────────┘   │
  │                               │ UNIX socket  │
  │              ┌────────────────▼──────────┐  │
  │              │  Coordinator              │  │
  │              │  finchrender-coordinator  │  │
  │              │  /run/finchrender/        │  │
  │              │  coordinator.sock         │  │
  │              └────────────────┬──────────┘  │
  │                               │             │
  │   ┌───────────────────────────▼──────────┐  │
  │   │  Cache Manager                       │  │
  │   │  finchrender-cache                   │  │
  │   │  /var/cache/finchrender/{tiles,      │  │
  │   │   frames,shaders}                    │  │
  │   └──────────────────────────────────────┘  │
  └────────────────────────┬────────────────────┘
                           │ UNIX sockets (per worker)
              ┌────────────┼────────────┐
              │            │            │
   ┌──────────▼──┐  ┌──────▼──────┐  ┌─▼────────────┐
   │ prod-render  │  │ prod-render  │  │ prod-render  │
   │     -01      │  │     -09      │  │     -14      │
   │ Gen1 RTX3090 │  │ Gen2 RTX4090 │  │ Gen2 RTX4090 │
   └─────────────┘  └─────────────┘  └─────────────┘
   10.100.2.1       10.100.2.9       10.100.2.14
```

## Coordinator Process

The `finchrender-coordinator` binary is a single-threaded event loop process that:
- Accepts connections from worker nodes, the gateway, and the cache manager on a UNIX socket
- Maintains an in-memory priority job queue
- Decomposes render jobs into tiles and dispatches them to available workers
- Tracks tile completion and assembles completed frames in the frame cache

**Runtime identity**: `finchrender` user (uid 2771), `render` group (gid 2001)  
**Socket**: `/run/finchrender/coordinator.sock`  
**Capabilities**: `CAP_SYS_NICE`, `CAP_NET_BIND_SERVICE`

## Data Flow

```
Artist submits job
  → Gateway validates and enqueues → Coordinator
  → Coordinator decomposes into tiles
  → Tiles dispatched to workers → Workers render tiles
  → Tile outputs written to /var/cache/finchrender/tiles/
  → Coordinator assembles tiles into frames
  → Frames written to /var/cache/finchrender/frames/
  → Coordinator notifies gateway → Gateway notifies artist
```

## Cache Architecture

```
/var/cache/finchrender/
  tiles/      ← in-progress tile renders (transient; cleared on coordinator restart)
  frames/     ← assembled frame buffers (transient; LRU eviction at 400 GB)
  shaders/    ← compiled GPU shader programs (cached; cleared on coordinator restart)
```

Cache directories are opened by the coordinator at startup and held open throughout the
coordinator's lifetime. Directory handles (file descriptors 6, 7, 8 in the lsof output) are
used for atomic `openat(dirfd, filename)` operations.
