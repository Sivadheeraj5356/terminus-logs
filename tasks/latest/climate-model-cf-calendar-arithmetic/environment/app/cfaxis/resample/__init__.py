"""Dataset resampling orchestration."""

from __future__ import annotations

from pathlib import Path

from cfaxis.formats import read_dataset, write_ccf
from cfaxis.formats.io import FormatArg, FreqArg
from cfaxis.resample import agg, bins, cache


def resample_dataset(
    input_path: Path,
    freq: FreqArg,
    output: Path,
    cache_dir: Path,
    use_cache: bool,
) -> None:
    ds = read_dataset(input_path, FormatArg.AUTO)
    key = cache.cache_key(ds, freq)
    if use_cache:
        cached = cache.load_cached(cache_dir, key)
        if cached is not None:
            write_ccf(output, cached)
            return
    binned = bins.assign_bins(ds, freq)
    aggregated = agg.aggregate_bins(ds, binned, freq)
    if use_cache:
        cache.store_cached(cache_dir, key, aggregated)
    write_ccf(output, aggregated)
