"""CLI entry point for cfaxis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cfaxis.append import append_datasets
from cfaxis.calaxis import run_axis
from cfaxis.error import ClimError
from cfaxis.formats import read_dataset, write_dataset
from cfaxis.formats.io import FormatArg, FreqArg
from cfaxis.provenance import dataset_provenance
from cfaxis.resample import resample_dataset
from cfaxis.trace import run_trace
from cfaxis.validate import validate_file


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "convert":
            inp = Path(args.input)
            outp = Path(args.out)
            if args.verbose:
                print(f"convert {inp} -> {outp}", file=sys.stderr)
            from_fmt = FormatArg(args.from_fmt)
            to_fmt = FormatArg(args.to_fmt)
            ds = read_dataset(inp, from_fmt)
            write_dataset(outp, ds, to_fmt)
            if args.verbose:
                print(f"provenance: {dataset_provenance(ds)}", file=sys.stderr)
        elif args.command == "append":
            base_path = Path(args.base)
            append_path = Path(args.append)
            out_path = Path(args.out)
            if args.verbose:
                print(
                    f"append {base_path} + {append_path} -> {out_path}",
                    file=sys.stderr,
                )
            base_ds = read_dataset(base_path, FormatArg.AUTO)
            append_ds = read_dataset(append_path, FormatArg.AUTO)
            append_datasets(base_ds, append_ds, out_path)
        elif args.command == "resample":
            inp = Path(args.input)
            outp = Path(args.out)
            cache = Path(args.cache_dir) if args.cache_dir else Path("/var/lib/climconvert/cache")
            if args.verbose:
                print(f"resample {inp} freq={args.freq} -> {outp}", file=sys.stderr)
            resample_dataset(
                inp,
                FreqArg(args.freq),
                outp,
                cache,
                not args.no_cache,
            )
        elif args.command == "trace":
            manifest_path = Path(args.manifest)
            out_path = Path(args.out)
            if args.verbose:
                print(f"trace manifest={manifest_path} out={out_path}", file=sys.stderr)
            run_trace(manifest_path, out_path)
        elif args.command == "compact":
            manifest_path = Path(args.manifest)
            if args.verbose:
                print(f"compact manifest={manifest_path}", file=sys.stderr)
            run_axis(manifest_path, use_cache=not args.no_cache)
        elif args.command == "validate":
            inp = Path(args.input)
            validate_file(inp)
            if args.verbose:
                print(f"validate OK: {inp}", file=sys.stderr)
        else:
            parser.error("no command specified")
    except ClimError as e:
        print(f"climconvert error: {e}", file=sys.stderr)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="climconvert", description="Climate cube format converter")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-cache", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    convert = sub.add_parser("convert")
    convert.add_argument("--in", dest="input", required=True)
    convert.add_argument("--out", required=True)
    convert.add_argument("--from", dest="from_fmt", default="auto", choices=["auto", "ccf", "cft"])
    convert.add_argument("--to", dest="to_fmt", default="auto", choices=["auto", "ccf", "cft"])

    append = sub.add_parser("append")
    append.add_argument("--base", required=True)
    append.add_argument("--append", dest="append", required=True)
    append.add_argument("--out", required=True)

    resample = sub.add_parser("resample")
    resample.add_argument("--in", dest="input", required=True)
    resample.add_argument("--freq", required=True, choices=["mon", "sea", "ann"])
    resample.add_argument("--out", required=True)
    resample.add_argument("--cache-dir", dest="cache_dir")

    trace = sub.add_parser("trace")
    trace.add_argument("--manifest", required=True)
    trace.add_argument("--out", required=True)

    compact = sub.add_parser("compact")
    compact.add_argument("--manifest", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--in", dest="input", required=True)

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
