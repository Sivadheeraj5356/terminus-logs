#!/usr/bin/env python3
"""Attach COLRv1 + CPAL from Asterism color sources onto a compiled TTF."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.ttLib import TTFont


def main() -> int:
    ttf, color_dir, out = sys.argv[1:4]
    color_path = Path(color_dir)
    font = TTFont(ttf)

    palettes_doc = tomllib.loads((color_path / "palettes.toml").read_text(encoding="utf-8"))
    palette_list = []
    palette_names = []
    for pal in palettes_doc.get("palette", []):
        palette_names.append(pal["name"])
        colors = []
        for c in pal.get("color", []):
            colors.append(
                (
                    float(c.get("red", 0)),
                    float(c.get("green", 0)),
                    float(c.get("blue", 0)),
                    float(c.get("alpha", 1)),
                )
            )
        palette_list.append(colors)

    font["CPAL"] = buildCPAL(palette_list)

    color_glyphs = {
        "comet": {"Format": 2, "PaletteIndex": 1, "Alpha": 1.0},
        "eclipse": {
            "Format": 4,
            "ColorLine": {
                "Extend": "pad",
                "ColorStop": [
                    {"StopOffset": 0.0, "Alpha": 1.0, "PaletteIndex": 1},
                    {"StopOffset": 1.0, "Alpha": 1.0, "PaletteIndex": 2},
                ],
            },
            "x0": 0.0,
            "y0": 0.0,
            "x1": 1000.0,
            "y1": 0.0,
            "x2": 0.0,
            "y2": 700.0,
        },
        "orbit": {
            "Format": 12,
            "Paint": {"Format": 2, "PaletteIndex": 2, "Alpha": 1.0},
            "Transform": {
                "xx": 0.85,
                "yx": 0.0,
                "xy": 0.0,
                "yy": 0.85,
                "dx": 50.0,
                "dy": 40.0,
            },
        },
        "signal": {"Format": 2, "PaletteIndex": 1, "Alpha": 1.0},
    }
    font["COLR"] = buildCOLR(color_glyphs, version=1)

    try:
        for i, pname in enumerate(palette_names):
            font["name"].setName(pname, 256 + i, 3, 1, 0x409)
        if hasattr(font["CPAL"], "paletteLabels"):
            font["CPAL"].paletteLabels = [256 + i for i in range(len(palette_names))]
    except Exception:
        pass

    font.save(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
