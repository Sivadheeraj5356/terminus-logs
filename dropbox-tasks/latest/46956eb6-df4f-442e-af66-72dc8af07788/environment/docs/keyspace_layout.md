# LMDB keyspace layout (development reference)

## samples

```
|<--- 8 bytes PID BE --->|<--- 8 bytes ts_ns BE --->|
```

Value: JSON with `cpu_pct`, `rss_kb`, `state`.

## errors

```
|<--- 8 bytes ts_ns BE --->|<--- 4 bytes seq BE --->|
```

The leading eight bytes are the nanosecond error timestamp used for correlation lookback. The trailing four bytes are a sequence disambiguator only.

Value: JSON with `pid`, `code`, `msg`.

## restarts

```
|<--- 8 bytes PID BE --->|
```

Value: JSON with `generation`, `reason`, `restart_ts`.
