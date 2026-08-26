# TERMINUS MEDIA ENGINEERING — ASSET PROCESSING SPECIFICATION

## Document Control

**Document Title:** CDN Derivative Build Specification
**Document Number:** TME-APS-014
**Revision:** 6.3.0
**Status:** Released
**Classification:** Internal Engineering Reference
**Owning Team:** Media Platform Engineering, Terminus Retail Systems

---

## Preamble and Scope

This document is the authoritative specification for the derivative build pipeline
that turns vendor-submitted product and marketing imagery into the fixed set of
web and CDN derivatives our storefronts, emails, and partner feeds consume. It
covers every rule needed to go from a raw vendor drop to a conformant derivative
set: how a source image is classified, how camera and scanner orientation is
normalized, how each asset class picks between cropping and fitting, how target
dimensions are computed and rounded, how color profiles are handled, how output
files are named, how the build manifest is structured and ordered, and what
"deterministic" means for this pipeline in concrete, testable terms.

This specification is written for the engineer implementing or maintaining the
`derive` build tool, and it is meant to be read start to finish. A number of the
rules that most affect correctness — the required order of operations between
orientation normalization and geometry decisions, the rounding convention used
when a scale factor produces a fractional pixel count, the crop offset parity
used when an even split is not possible, and the handling of assets that already
conform to their target and must not be re-encoded — are stated once, in prose,
in the sections where they are architecturally relevant, rather than repeated in
every table.

Read together with this document: the CSV classification file shipped alongside
the source images (`manifest_inputs.csv`), and the canonical color profile file
shipped at `/app/assets/color_profiles/sRGB.icc`. Both are referenced throughout
this specification and neither is optional context — the classification file
determines which rules apply to which source, and the color profile file is the
literal byte sequence that must be embedded for any source that arrives without
an embedded profile of its own.

The remainder of this document is organized as follows. The Pipeline Overview
section establishes the high-level data flow and the required order of stages.
The Asset Classification section defines how sources are mapped to asset
classes and what to do with malformed classification rows. The Orientation
Normalization section defines the orientation values this pipeline must
handle, across every source container format, and, critically, when in the
pipeline orientation must be applied relative to every other geometry
decision. Five class-specific sections define
the exact target geometry, crop-vs-fit behavior, and per-class exceptions for
the `thumbnail`, `card`, `avatar`, `hero`, and `banner` asset classes. The
Rounding Convention section defines the single rounding rule used everywhere a
non-integer scale factor is applied to a source dimension. The Cover-Crop Offset
Parity section defines how the crop rectangle is centered when an even split is
not possible. The Color Profile and Colorspace Policy section defines when a
profile is preserved, when one must be assumed and embedded, and what operations
are forbidden. The Deterministic Encoding Requirements section defines the exact
encoder settings required for a second run to be byte-identical to the first.
The Already-Conformant Sources section defines how to handle a source that
already satisfies its target's geometry, orientation, and color policy. The
Naming Template section defines the exact filename-construction algorithm,
including how non-ASCII bytes in a source's filename must be handled. The
Manifest Schema section defines the JSON structure, field types, and
deterministic ordering key for `manifest.json`. The CLI Contract section
defines the command-line interface `derive` must expose. A Validation Rule
Reference section enumerates numbered rules (`Rule OR-001`, `Rule CV-002`, and
so on) referenced elsewhere in the document. Appendices provide a glossary, a
field-by-field manifest reference, and background on the ICC profile byte
format.
---

## 1. Pipeline Overview

The derivative build pipeline is a single-pass batch tool. Given a directory of
vendor source images, a CSV file mapping each source filename to an asset class,
and this specification, the tool must produce exactly one derivative for every
row of the classification CSV, plus a single manifest file describing what was
produced. The pipeline has no interactive component and takes no action other
than reading its inputs and writing its outputs; it must never modify anything
under the source asset directory.

Conceptually, each source file passes through the following stages, always in
this order:

1. **Classification lookup.** The source filename is looked up in the
   classification CSV to determine its asset class. Every row in the CSV must
   produce exactly one derivative; the tool must not skip rows, must not invent
   derivatives for files that are not listed in the CSV, and must not silently
   drop a row because the corresponding file is awkward to process (for example,
   because its filename contains non-ASCII bytes, or because it is already at
   its target geometry).

2. **Orientation normalization.** The source is read and its orientation
   metadata, if any, is applied so that the pixel data is physically rotated
   (and, where applicable, its width and height are swapped) to match how the
   image is meant to be displayed. This stage MUST run before any stage that
   makes a decision based on the source's width or height. This ordering
   requirement is restated and elaborated in Section 2.

3. **Asset-class geometry.** Once orientation has been normalized, the
   corrected width and height are used to compute the target derivative
   geometry according to the rule for the source's asset class (Sections 3
   through 7). Every asset class is either a **cover** class, which crops to an
   exact fixed pixel target, or a **fit** class, which scales to fit within a
   bounding box while preserving aspect ratio and never letterboxes (pads) the
   result.

4. **Color profile and colorspace policy.** Depending on whether the
   orientation-normalized source already carries an embedded ICC color profile,
   the pipeline either preserves that profile unchanged or embeds the canonical
   sRGB profile shipped at `/app/assets/color_profiles/sRGB.icc`. This stage is
   defined fully in Section 11.

5. **Deterministic encoding.** The final pixel data is encoded to the output
   file using the fixed encoder settings in Section 12, so that running the
   whole pipeline twice against unchanged inputs produces byte-for-byte
   identical output files and an unchanged manifest.

6. **Already-conformant shortcut.** Before any of stages 2 through 5 alter a
   source's bytes, the pipeline must check whether the source, exactly as
   shipped, already satisfies every property its asset class requires:
   correct final geometry, normalized orientation, and a correctly-policied
   color profile. If it does, the tool must copy the source bytes to the
   output location unchanged rather than routing it through the encoder again.
   Section 13 explains why this matters and how to detect this case correctly.

7. **Naming and hashing.** The output file is named according to the
   deterministic template in Section 14, and a SHA-256 digest is computed over
   the final output bytes for inclusion in the manifest.

8. **Manifest emission.** After every row of the classification CSV has been
   processed, a single `manifest.json` is written, listing one entry per
   derivative, in the deterministic order defined in Section 15, never in
   filesystem enumeration order.
---

## 2. Orientation Normalization

Vendor sources may carry orientation metadata indicating how the stored
raster must be rotated and/or mirrored to reach display orientation, with any
of the eight standard values below. This requirement is format-independent:
JPEG-family sources convey this via the standard EXIF `Orientation` tag (tag
`0x0112`), and TIFF-family sources convey the equivalent information via
TIFF's own native Orientation tag (the same tag number and the same eight
values, since EXIF's tag numbering is derived from TIFF's). A tool that only
recognizes the JPEG-style EXIF block will silently miss orientation metadata
carried natively by a TIFF source. This pipeline's shipped source set
exercises three of the eight values, and the tool must handle all eight
correctly, across every container format it processes, since future vendor
drops may use any of them:

- **Orientation 1** (or the tag absent entirely): the stored raster is already
  in display orientation. No rotation is needed.
- **Orientation 3**: the stored raster is rotated 180 degrees relative to
  display orientation. Width and height are unaffected; every pixel must be
  rotated 180 degrees (equivalently, flipped both horizontally and vertically).
- **Orientation 6**: the stored raster must be rotated 90 degrees clockwise to
  reach display orientation. The stored width becomes the display height and
  the stored height becomes the display width — width and height are swapped.
- **Orientation 8**: the stored raster must be rotated 90 degrees
  counter-clockwise (270 degrees clockwise) to reach display orientation.
  As with orientation 6, width and height are swapped.
- **Orientation 2**: the stored raster is mirrored left-to-right (a horizontal
  flip) relative to display orientation. Width and height are unaffected.
- **Orientation 4**: the stored raster is mirrored top-to-bottom (a vertical
  flip) relative to display orientation. Width and height are unaffected.
- **Orientation 5**: the stored raster must be reflected across its main
  diagonal (the line from the top-left corner to the bottom-right corner) to
  reach display orientation. Width and height are swapped; the pixel at
  the top-left corner stays at the top-left corner, the pixel at the
  bottom-right corner stays at the bottom-right corner, and the top-right and
  bottom-left corners exchange places.
- **Orientation 7**: the stored raster must be reflected across its
  anti-diagonal (the line from the top-right corner to the bottom-left
  corner) to reach display orientation. Width and height are
  swapped; the pixel at the top-right corner stays at the top-right corner,
  the pixel at the bottom-left corner stays at the bottom-left corner, and
  the top-left and bottom-right corners exchange places. The distinguishing
  detail between orientations 5 and 7 is which pair of corners stays fixed
  (main-diagonal corners for 5, anti-diagonal corners for 7) and which pair
  exchanges.
- Orientations 2, 4, 5, and 7 are not present in the currently shipped source
  set but must still be normalized correctly by any general-purpose
  implementation.

**The load-bearing rule of this section is ordering, not the rotation math
itself:** orientation normalization must be the very first transformation
applied to a source's pixel data, and every later stage — asset-class geometry
selection, scale-factor computation, crop-rectangle computation — must operate
on the *post-normalization* width and height, never the raster's stored,
pre-rotation width and height. Concretely, if a source's stored raster is
`stored_w` by `stored_h` and its orientation tag calls for a 90-degree family
rotation (values 5, 6, 7, or 8), then the width and height used for every
subsequent computation in this specification — scale factor, target dimension
rounding, crop rectangle, fit-box comparison — must be `stored_h` by `stored_w`,
i.e. swapped, not `stored_w` by `stored_h`.

**Rule OR-001:** Orientation normalization must run before asset-class geometry
selection for every source, regardless of asset class.

**Rule OR-002:** For orientation values in {5, 6, 7, 8}, every later
computation must use the swapped (width, height) pair. For orientation values
in {1, 2, 3, 4} (or an absent tag), width and height are unaffected by
orientation.

**Rule OR-003:** The output derivative must not carry a non-trivial EXIF
orientation tag. Either the tag must be absent, or it must be present with
value 1. A tool that copies the source's original orientation tag verbatim
into the output — even though it has already physically rotated the pixels —
produces a file that most viewers will render rotated a second time, which is
incorrect.
---

## 3. Asset Classification

Each source file's asset class is determined by looking up its filename in
`manifest_inputs.csv`, which is a two-column CSV with a header row:
`filename,asset_class`. The `filename` column gives the source's filename
exactly as it appears under the source asset directory (not a path — just the
filename, matched byte-for-byte including any non-ASCII bytes the filename may
contain). The `asset_class` column gives one of the five class names defined
in Sections 4 through 8: `thumbnail`, `card`, `avatar`, `hero`, or `banner`.

**Rule CL-001:** Every row in the classification CSV must produce exactly one
derivative in the output set. The tool must not omit a row's derivative for any
reason, including because the row's filename contains bytes outside the ASCII
range, because the source file is already at its target geometry, or because
the source file happens to be small. There is no class of "skip this one" file.

**Rule CL-002:** The tool must not produce derivatives for files present under
the source asset directory but absent from the classification CSV. The CSV is
the exhaustive, authoritative list of what to process.

**Rule CL-003:** Filenames in the classification CSV, and the corresponding
files on disk, may contain multi-byte UTF-8 sequences (for example, a filename
containing an accented Latin letter). Implementations must treat filenames as
opaque byte sequences for the purposes of matching them against the CSV and
locating the file on disk. Do not assume a filename is pure ASCII, and do not
perform any byte-by-byte case transformation on a filename using a lookup
table or comparison that is only valid for the signed range of `char` on the
build platform — a byte with its high bit set (any byte with numeric value
128 or greater) is a valid, meaningful part of a UTF-8 filename and must be
copied through unchanged wherever this specification calls for preserving
non-ASCII bytes verbatim (see Section 14, the Naming Template).

**Rule CL-004:** The classification CSV in this shipped environment has no
malformed rows, no duplicate filenames, and no filenames referencing a class
outside the five defined in this specification. A general-purpose
implementation should still fail loudly (non-zero exit code, no output written)
rather than guessing, if it ever encounters an asset class name it does not
recognize, since a silent default would misapply another class's geometry
rule without any indication in the tool's output.
---

## 4. Asset Class: `thumbnail`

The `thumbnail` class produces small, exactly-square previews used in
search result grids and cart line items. Because these previews sit in a fixed
grid cell, the derivative must be exactly the target pixel dimensions on both
axes — there is no acceptable "close enough" size. This is a **cover** class:
the source is scaled up (never down below the target) until it fully covers
the target rectangle on both axes, and the overhanging excess is cropped away
symmetrically per the offset parity rule in Section 8.

| Property | Value |
|---|---|
| Mode | cover (crop to exact target) |
| Target width | 320 px |
| Target height | 320 px |
| Upscale allowed | yes |
| Downscale allowed | yes |

**Rule TH-001:** The output derivative for a `thumbnail`-class source must
be exactly 320 by 320 pixels, regardless of the source's own aspect ratio.

**Rule TH-002:** The scale factor is chosen so that the scaled source covers
the full 320-by-320 target on both axes with no gap on either axis (see
Section 7, cover-mode scale factor selection), and the crop is centered per
Section 8.
---

## 5. Asset Class: `card`

The `card` class produces the fixed-aspect preview used in the storefront
product grid and in transactional emails. Unlike `thumbnail`, the target
rectangle is not square, so the crop direction (trimming more from the top and
bottom versus the left and right) depends on how the source's aspect ratio
compares to the target's. This is a **cover** class.

| Property | Value |
|---|---|
| Mode | cover (crop to exact target) |
| Target width | 640 px |
| Target height | 400 px |
| Upscale allowed | yes |
| Downscale allowed | yes |

**Rule CD-001:** The output derivative for a `card`-class source must be
exactly 640 by 400 pixels.

**Rule CD-002:** Because 640-by-400 is a 8:5 aspect ratio, sources that are
themselves wider than 8:5 will have their crop excess entirely on the
horizontal axis, and sources narrower (more portrait) than 8:5 will have their
crop excess entirely on the vertical axis, but implementations must compute
the excess on **both** axes generally (Section 7) rather than special-casing
"wide" versus "tall" sources, since the general cover-mode formula already
produces zero excess on whichever axis the scale factor exactly satisfies.
---

## 6. Asset Class: `avatar`

The `avatar` class produces small square profile images. Like
`thumbnail`, it is a **cover** class, but with a smaller target used in
compact UI contexts such as review bylines and account menus.

| Property | Value |
|---|---|
| Mode | cover (crop to exact target) |
| Target width | 200 px |
| Target height | 200 px |
| Upscale allowed | yes |
| Downscale allowed | yes |

**Rule AV-001:** The output derivative for an `avatar`-class source must
be exactly 200 by 200 pixels.

**Rule AV-002:** `avatar` uses the same cover-mode scale and crop formulas as
`thumbnail` and `card` (Sections 7 and 8); only the target dimensions differ.
---

## 7. Asset Class: `hero`

The `hero` class produces the large background image used behind
storefront landing-page headers. Unlike the cover classes above, `hero` must
never crop any part of the source out of frame — landing-page art directors
compose these images edge-to-edge and a crop would cut off intentional
composition elements. `hero` is therefore a **fit** class: the source is
scaled, preserving its aspect ratio, to fit entirely within a bounding box,
and the derivative's own dimensions are whatever the scaled result turns out
to be (there is no letterboxing or padding to force the output to the box's
exact dimensions). `hero` additionally has a **shrink-only** restriction:
because hero art is always submitted at high resolution, this class must never
upscale a source past the bounding box's dimensions, even if the source is
smaller than the box on both axes.

| Property | Value |
|---|---|
| Mode | fit (scale to bounding box, preserve aspect, no letterbox) |
| Bounding box width | 1920 px |
| Bounding box height | 1080 px |
| Upscale allowed | **no (shrink-only)** |
| Downscale allowed | yes |

**Rule HR-001:** Compute the fit-mode scale factor per Section 7 using
the 1920-by-1080 bounding box.

**Rule HR-002:** If the computed scale factor is greater than 1.0 (meaning the
source, on both axes, is already smaller than the bounding box), clamp the
scale factor to exactly 1.0 instead. The output dimensions in this case are
the source's own orientation-normalized width and height, completely
unmodified — not resized at all, in either direction. A `hero` source that is
already smaller than its bounding box is emitted at its native size.

**Rule HR-003:** Do not letterbox, pad, or canvas-extend the output to force
it to exactly 1920 by 1080. The `hero` output's own dimensions vary from
source to source and are exactly the result of Rule HR-001/HR-002's scale
factor applied to the orientation-normalized source dimensions, rounded per
Section 7.
---

## 8. Asset Class: `banner`

The `banner` class produces the wide promotional strip used at the top
of category pages and in the mobile app's rotating carousel. Like `hero`, it
is a **fit** class that never crops. Unlike `hero`, `banner` source art is
frequently submitted undersized relative to the carousel's display box (art
teams often supply a banner authored at exactly carousel size, or smaller, and
expect the pipeline to scale it up to fit), so `banner` does **not** have the
shrink-only restriction: upscaling is required behavior for undersized
sources, not an error case to guard against.

| Property | Value |
|---|---|
| Mode | fit (scale to bounding box, preserve aspect, no letterbox) |
| Bounding box width | 1200 px |
| Bounding box height | 300 px |
| Upscale allowed | **yes** |
| Downscale allowed | yes |

**Rule BN-001:** Compute the fit-mode scale factor per Section 7 using
the 1200-by-300 bounding box. Unlike `hero`, do not clamp a scale factor
greater than 1.0 — apply it as computed, upscaling the source if necessary.

**Rule BN-002:** As with `hero`, do not letterbox, pad, or canvas-extend the
output. The `banner` output's dimensions are exactly the result of the scale
factor applied to the orientation-normalized source dimensions, rounded per
Section 7.
---

## 9. Scale Factor and Rounding Convention

This section defines, once, the arithmetic used by every asset class in
Sections 4 through 8 to go from a source's orientation-normalized width and
height to a derivative's pixel dimensions. Every class-specific section above
refers back to this one; there is no per-class variation in the rounding rule
itself, only in which scale factor formula (cover vs. fit) and which target or
bounding-box constants apply.

### 9.1 Cover-mode scale factor

For a **cover** class (`thumbnail`, `card`, `avatar`) with target width `tw`
and target height `th`, and an orientation-normalized source of width `sw` and
height `sh`, the scale factor is:

    scale = max(tw / sw, th / sh)

Using `max` (rather than `min`) is what makes this a *cover* rule: it selects
the smaller of the two possible crop margins, guaranteeing the scaled source
is at least as large as the target on both axes, so that a centered crop to
the exact target is always possible without any gap.

### 9.2 Fit-mode scale factor

For a **fit** class (`hero`, `banner`) with bounding box width `bw` and
bounding box height `bh`, and an orientation-normalized source of width `sw`
and height `sh`, the scale factor is:

    scale = min(bw / sw, bh / sh)

Using `min` (rather than `max`) is what makes this a *fit* rule: it selects the
larger of the two possible margins, guaranteeing the scaled source fits
entirely within the box on both axes with no overhang, at the cost of the
scaled result exactly touching only one of the two box edges (the other axis
falls short of the box, which is expected and must not be padded — see Rule
HR-003 / BN-002).

For `hero` specifically, if this computed scale factor exceeds 1.0, it must
be clamped to 1.0 per Rule HR-002 before proceeding to Section 9.3. For
`banner`, no such clamp is applied (Rule BN-001).

### 9.3 Rounding: floor-with-tie

Applying a scale factor to an integer source dimension almost never produces
an integer result. This pipeline uses a single rounding rule, applied
independently to the scaled width and the scaled height, called
**floor-with-tie**:

Given a raw scaled value `x` (a non-negative real number), let `f` be the
mathematical floor of `x` (the largest integer not greater than `x`), and let
`frac = x - f` be the fractional remainder. Then:

- If `frac` is exactly `0.5` (an exact tie between `f` and `f + 1`), the
  rounded result is `f + 1` (round the tie up).
- In every other case — `frac` less than `0.5` or greater than `0.5` — the
  rounded result is simply `f` (floor).

This is deliberately **not** the same as "round half away from zero" or
"round half to even" (banker's rounding) applied generally, because those
rules also change the result for values whose fractional part is close to but
not exactly `0.5` due to floating-point representation error; nor is it plain
`floor()` applied unconditionally, because that would produce an off-by-one
result relative to the intended convention on the not-infrequent occasions
where a scale factor and a source dimension multiply out to a mathematically
exact `.5` (this happens whenever the source dimension is even and the scale
factor's denominator, in lowest terms, is exactly 2 — which arises naturally
from bounding boxes and targets that are themselves even numbers, as all of
this specification's targets and boxes are). Implementations must apply exact
tie detection (for example, by working with the scale factor and source
dimension as an exact rational number — a numerator/denominator pair of
integers — rather than propagating floating-point rounding error through the
comparison), because a naive floating-point `frac == 0.5` comparison can
silently fail to detect a tie that is mathematically exact but not exactly
representable, or can spuriously detect a tie that is not exact due to
accumulated multiplication error. A reliable implementation computes the
scaled numerator and denominator as integers (for cover mode: numerator is
`sw * th` or `sh * th`-style cross products depending on which axis the
`max()` selected, denominator from the other target/source pair) and performs
the floor/tie test using integer arithmetic, never floating point, before any
rounding decision is made.

**Rule RD-001:** Apply floor-with-tie independently to the scaled width and
the scaled height. A tie on one axis does not imply or require a tie on the
other.

**Rule RD-002:** Perform tie detection using exact (rational/integer)
arithmetic. Do not rely on floating-point equality against `0.5`.
---

## 10. Cover-Crop Offset Parity

Once a cover-mode scale factor (Section 9.1) has been applied to the source's
orientation-normalized width and height, using floor-with-tie rounding
(Section 9.3), the result is a scaled image whose width is greater than or
equal to the target width, and whose height is greater than or equal to the
target height (this is guaranteed by the `max()` in the cover-mode scale
factor). Exactly one axis is typically an exact match (zero excess) and the
other has some non-negative excess to trim away, though in principle both can
have zero excess simultaneously (when the source's aspect ratio exactly
matches the target's).

Let `excess_w = scaled_w - target_w` and `excess_h = scaled_h - target_h`
(both are non-negative integers). The crop rectangle's top-left corner,
measured in pixels from the scaled image's own top-left corner, is:

    left = excess_w // 2   (integer division, i.e. floor(excess_w / 2))
    top  = excess_h // 2   (integer division, i.e. floor(excess_h / 2))

and the crop rectangle's dimensions are exactly `target_w` by `target_h`.

When `excess_w` (or `excess_h`) is even, this centers the crop exactly, with
equal margins trimmed from both sides. When `excess_w` (or `excess_h`) is odd
— which happens whenever the scaled dimension and the target dimension have
different parity — an exactly even split is impossible, and this pipeline's
convention is to put the *smaller* half of the margin on the left/top and the
*larger* (one-pixel-larger) half on the right/bottom. Equivalently: **the
single extra pixel of an odd excess is always trimmed from the right edge
(for a horizontal excess) or the bottom edge (for a vertical excess), never
from the left or top edge.**

**Rule CR-001:** `left = excess_w // 2` and `top = excess_h // 2`, using
floor/truncating integer division, for both even and odd excess values.

**Rule CR-002:** The crop rectangle is exactly `target_w` by `target_h`
pixels, positioned at `(left, top)` within the scaled (post floor-with-tie
rounding) image. A crop rectangle computed from any other rounding of
`excess_w / 2` or `excess_h / 2` — for example, rounding to nearest, or
consistently favoring the left/top edge for the extra pixel — does not match
this pipeline's convention and will be detected by pixel-level comparison
against the correct sub-rectangle, not merely by comparing output dimensions
(which are always exactly the target regardless of which edge the extra pixel
was trimmed from).
---

## 11. Color Profile and Colorspace Policy

Vendor sources arrive in two states with respect to color management: some
already carry an embedded ICC color profile (typically because the vendor's
own export pipeline tags its output), and some carry no profile at all. This
pipeline's policy is deliberately asymmetric between these two cases: the two
cases must not be normalized to the same handling.

**If the orientation-normalized source already carries an embedded ICC
profile,** that exact profile — the same bytes, unmodified — must be present
in the output derivative. Do not replace it, do not convert it to a different
profile, do not re-tag the colorspace, and do not strip it. The profile
travels through the pipeline unchanged regardless of which asset class the
source belongs to or how much resizing/cropping is applied to the pixel data.

**If the orientation-normalized source carries no embedded ICC profile,**
the pipeline must assume the source's pixel data is already in sRGB and must
embed the canonical sRGB profile shipped at
`/app/assets/color_profiles/sRGB.icc` into the output derivative. This is not
optional metadata hygiene — downstream color-managed rendering paths (several
of the storefront's image viewers, and all of the print-catalog export path)
treat the absence of an embedded profile as "assume the display's own profile"
rather than "assume sRGB," which produces visibly wrong colors on wide-gamut
displays for untagged imagery. Embedding the canonical profile is what makes
untagged sources render correctly everywhere; converting their pixel data
instead of tagging it, or skipping this step because "the pixels are probably
sRGB already," are both incorrect.

**Rule IC-001:** A source with an embedded ICC profile must produce a
derivative whose embedded ICC profile is byte-for-byte identical to the
source's embedded profile.

**Rule IC-002:** A source with no embedded ICC profile must produce a
derivative whose embedded ICC profile is byte-for-byte identical to
`/app/assets/color_profiles/sRGB.icc` as shipped in this environment.

**Rule IC-003:** Stripping all metadata (including the color profile) from
the output — for example, via a blanket "strip everything" cleanup pass
intended to shrink file size or remove EXIF/GPS metadata — is forbidden. Any
operation that removes the embedded profile violates Rule IC-001 for
previously-tagged sources and produces an output with no profile at all for
previously-untagged sources, which violates Rule IC-002 (an untagged output is
not the same as an output tagged with the canonical profile, even though
downstream consumers sometimes assume untagged input is sRGB — Rule IC-002
requires an explicit embedded profile, not an implicit assumption baked into
some downstream consumer).

**Rule IC-004:** Colorspace conversion (for example, converting a source's
color values from one gamut to another, as opposed to simply tagging or
preserving a profile) is out of scope for this pipeline and must not be
performed. The pixel values themselves are never renumbered by the color
policy in this section — only the embedded profile bytes are added, preserved,
or (incorrectly, if attempted) removed.
---

## 12. Deterministic Encoding Requirements

Running the pipeline twice against an unchanged source asset directory and
classification CSV must produce byte-for-byte identical output files and an
unchanged `manifest.json` (including an unchanged SHA-256 digest for every
derivative). This is a strict requirement, checked directly by re-running the
whole tool and comparing outputs, not merely by comparing reported metadata
such as width and height.

Byte-for-byte reproducibility across runs is not automatic. General-purpose
image encoders default to settings that are reproducible within a single
build/version of the encoder but that also, by default, embed information that
has nothing to do with the pixel data and everything to do with when the
encoder ran — timestamps, in particular. A derivative build tool that uses an
encoder's default settings unmodified will typically produce different bytes
on every run even though every pixel is identical, because a written
timestamp (or similar incidental field) differs between runs. The following
settings are required, per output container format, to eliminate every
source of run-to-run byte drift this pipeline is aware of:

**For PNG outputs:** disable writing of the `tIME` chunk (which records a
last-modification timestamp) and the textual `date`/`time` fields some
encoders write into ancillary chunks; use a fixed compression level (this
pipeline standardizes on the encoder's maximum compression level) and a fixed
adaptive filter selection strategy, not "encoder's best guess for this image"
heuristics that can vary run to run for reasons unrelated to the pixel data.

**For JPEG outputs:** use a fixed quality setting (this pipeline standardizes
on quality 85 on the encoder's 0-100 scale) and a fixed 4:2:0 chroma
subsampling mode, and do not embed a "date created" or similar comment
field. JPEG encoding at a fixed quality setting, with a fixed chroma
subsampling mode and a fixed DCT method, is deterministic run-to-run for
identical input pixels as long as no incidental timestamp/comment metadata
is added on top of the compressed image data.

**For TIFF outputs:** use a fixed compression scheme (this pipeline does not
require TIFF outputs from any of its five asset classes given the naming rule
in Section 13, which normalizes the output container to match the source
container family — but if a TIFF source's asset class or future class
additions ever require a TIFF output, the same "no incidental timestamp
fields" requirement applies).

**Resize filter:** every resize or crop-scale operation performed by this
pipeline (both cover-mode scaling and fit-mode scaling) must use a fixed
resampling filter. This pipeline standardizes on the Lanczos filter for every
resize operation, regardless of asset class or scale direction (upscale or
downscale).

**Rule DT-001:** Two consecutive invocations of the pipeline against an
unchanged source directory and classification CSV must produce byte-for-byte
identical files under the output derivatives directory.

**Rule DT-002:** Two consecutive invocations must produce byte-for-byte
identical `manifest.json` files, including identical SHA-256 digest fields
for every entry.

**Rule DT-003:** No output file may contain an embedded timestamp, "date
created" field, or other value that varies between two runs performed at
different wall-clock times but against identical input bytes.
---

## 13. Already-Conformant Sources

Some vendor sources arrive already satisfying every requirement their asset
class imposes: the source's own pixel dimensions already exactly equal the
class's target (for a cover class) or already fit within the class's bounding
box at the source's native size in a way that a fit-mode computation would
leave unchanged, the source's EXIF orientation tag is already absent or
already normal (value 1, requiring no rotation), and the source's embedded
ICC profile already satisfies Section 11's policy for that source (already
correctly tagged, or already carrying the exact canonical profile if it was
always untagged and something upstream of this pipeline already embedded the
canonical profile before the source was submitted).

When every one of these conditions holds for a given source, the correct
output for that source is a byte-for-byte, unmodified copy of the source file
— not a re-encoding that merely happens to target the same final geometry.
This matters because passing an already-conformant source back through a
general-purpose image encoder, even when every requested output property
(dimensions, orientation, embedded profile) matches what the source already
has, does not generally reproduce the source's exact original bytes. Different
encoder implementations, different compression parameter defaults, and
different ancillary-chunk layouts all commonly produce a different byte
stream for pixel-identical content. A pipeline that routes every source
through the same encoding stage unconditionally will, for an already-conformant
source, silently change that source's bytes on the very first run, changing
the file's hash for no reason even though the pixels and reported dimensions
still look correct.

**Rule PC-001:** Before applying orientation normalization, geometry
transformation, or re-encoding, determine whether a source is already fully
conformant for its asset class: correct final geometry already achieved at
native size, no orientation correction needed, and its embedded-profile state
already satisfying Section 11 for that source. If so, copy the source's bytes
to the output location unchanged. Do not decode-and-re-encode an
already-conformant source even when doing so happens to preserve every
requested property.

**Rule PC-002:** Determining conformance requires checking geometry,
orientation, and color-profile state together — a source can satisfy some of
these conditions and not others (for example, correct dimensions but a
non-normal orientation tag, which still requires processing). Only a source
satisfying all applicable conditions simultaneously qualifies for the
byte-identical passthrough in Rule PC-001.

**Rule PC-003:** The passthrough decision does not change which asset class a
source belongs to, its filename in the output manifest, or its inclusion in
the deterministic ordering (Section 14). An already-conformant source still
produces exactly one manifest entry, named per Section 13's naming template,
in its normal position in the deterministic ordering — the only difference is
that the bytes written to the output path are copied rather than re-encoded.
---

## 14. Naming Template

Every derivative's output filename is constructed deterministically from its
source filename and asset class, following this exact template:

    {asset_class}__{transformed_stem}__{output_width}x{output_height}.{ext}

with a double underscore separating each of the three components, where:

- `{asset_class}` is the class name exactly as it appears in the
  classification CSV (`thumbnail`, `card`, `avatar`, `hero`, or `banner`).
- `{output_width}` and `{output_height}` are the derivative's final pixel
  dimensions (after Sections 9-10 for cover classes, or Sections 9 and 7-8 for
  fit classes), written as plain decimal integers with no leading zeros.
- `{ext}` is the normalized output container extension: `png` for a PNG
  source, `jpg` for a JPEG source (regardless of whether the source itself
  used the `.jpg` or `.jpeg` extension), and `tiff` for a TIFF source
  (regardless of whether the source itself used the `.tif` or `.tiff`
  extension). The output container format always matches the source's own
  container format family — this pipeline never transcodes between PNG,
  JPEG, and TIFF.
- `{transformed_stem}` is derived from the source filename with its original
  extension removed, transformed byte-by-byte according to the following
  algorithm:

For each byte of the source's filename stem (the filename with its extension
and the final `.` removed), in order:

1. If the byte is an ASCII uppercase letter (numeric value 0x41 through 0x5A
   inclusive, `'A'`-`'Z'`), append its ASCII lowercase equivalent (add 0x20).
2. Otherwise, if the byte is an ASCII lowercase letter, an ASCII digit, an
   underscore, or a hyphen (0x61-0x7A, 0x30-0x39, 0x5F, or 0x2D), append it
   unchanged.
3. Otherwise, if the byte has its high bit set (numeric value 0x80 or
   greater, meaning it is part of a multi-byte UTF-8 sequence and therefore
   not an ASCII byte at all), append it unchanged. Do not attempt to
   case-fold, transliterate, or otherwise interpret multi-byte UTF-8
   sequences — copy these bytes through exactly as they appear in the source
   filename.
4. Otherwise (the byte is some other ASCII byte — for example a space, a
   period other than the extension separator, or ASCII punctuation not listed
   in step 2), append a single hyphen (0x2D) in its place.

After this byte-by-byte pass, collapse any run of two or more consecutive
hyphens produced by step 4 into a single hyphen, and then strip any hyphen
that remains at the very start or the very end of the resulting string.

Because step 3 preserves high-bit bytes unconditionally and step 1's range
check only ever matches values in 0x41-0x5A, an implementation that performs
this byte classification using a signed 8-bit `char` type without first
converting each byte to `unsigned char` (or an equivalent unsigned integer
type) before comparing it against 0x80 or indexing any lookup table with it
is at risk of undefined behavior or an out-of-bounds table read for exactly
the filenames step 3 is meant to handle.

**Rule NM-001:** Apply the four-step byte transformation above to the source
filename's stem, in byte order, using unsigned byte comparisons throughout.

**Rule NM-002:** Collapse consecutive hyphens produced by step 4 into a
single hyphen, and strip any leading or trailing hyphen from the final
transformed stem.

**Rule NM-003:** The final output filename is
`{asset_class}__{transformed_stem}__{output_width}x{output_height}.{ext}`
exactly, with no additional path components, no case transformation applied
to `{asset_class}` itself (it is already lowercase in the CSV), and the
literal double-underscore separators shown above.
---

## 15. Manifest Schema and Ordering

The pipeline writes a single `manifest.json` file describing every derivative
it produced. The file is a single JSON object with a top-level `derivatives`
key holding an array of one object per derivative:

    {
      "derivatives": [
        {
          "source_file": "example_source.png",
          "asset_class": "thumbnail",
          "output_file": "thumbnail__example_source__320x320.png",
          "width": 320,
          "height": 320,
          "icc_policy": "assumed_srgb",
          "orientation_normalized": false,
          "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        }
      ]
    }

Field definitions:

- `source_file` (string): the source's filename exactly as it appears in the
  classification CSV, including any non-ASCII bytes.
- `asset_class` (string): one of the five class names.
- `output_file` (string): the derivative's filename, constructed per Section
  14. This is a bare filename, not a path — the derivative itself lives under
  the output derivatives directory, and the manifest does not repeat that
  directory prefix.
- `width`, `height` (integers): the derivative's final pixel dimensions.
- `icc_policy` (string): either the literal string `"preserved"` (the source
  already carried an embedded profile which was carried through unchanged) or
  the literal string `"assumed_srgb"` (the source carried no profile and the
  canonical sRGB profile was embedded per Rule IC-002).
- `orientation_normalized` (boolean): `true` if the source's EXIF orientation
  tag required a rotation to reach display orientation (i.e., the tag was
  present with a value other than 1), `false` if the source's tag was already
  1 or absent.
- `sha256` (string): the lowercase hexadecimal SHA-256 digest of the
  derivative's final output bytes, exactly as written to disk.

**Rule MF-001:** The manifest must contain exactly one entry per row of the
classification CSV — the same one-to-one correspondence required of the
output derivative files themselves (Rule CL-001).

**Rule MF-002:** Every field listed above must be present on every entry,
with the exact key names and JSON types shown (strings, integers, and a JSON
boolean — not the strings `"true"`/`"false"`).

**Rule MF-003 (ordering):** The `derivatives` array must be sorted in
ascending order primarily by `asset_class` (as a plain byte/lexicographic
string comparison: `avatar` before `banner` before `card` before `hero`
before `thumbnail`), and secondarily, within a shared `asset_class`, by the
`transformed_stem` computed in Section 14 (byte/lexicographic comparison, not
the original untransformed source filename, and not the `output_file` or
`source_file` field directly — sort by the same transformed stem value used
to build the output filename). This ordering must not depend on filesystem
directory-listing order, the order rows appear in the classification CSV, or
any other incidental iteration order — a correct implementation computes the
sort key explicitly and sorts by it, rather than relying on an iteration
order that happens to already match on this environment's filesystem.

**Rule MF-004:** The manifest file itself must be valid JSON, UTF-8 encoded,
and must be byte-for-byte reproducible across repeated runs against unchanged
inputs (Rule DT-002).
---

## 16. Command-Line Interface Contract

The build tool is a single executable, `derive`, invoked with the following
flags:

    derive --sources <source_dir> --csv <classification_csv> \
           --spec <this_spec_path> --out <output_dir>

- `--sources`: path to the directory containing vendor source image files
  (in this environment, `/app/assets/src`).
- `--csv`: path to the classification CSV described in Section 3 (in this
  environment, `/app/assets/src/manifest_inputs.csv`).
- `--spec`: path to this specification document (in this environment,
  `/app/spec/asset_processing_spec.md`). The tool is not required to
  literally parse this file at runtime, but is required to implement every
  rule this file defines.
- `--out`: path to the output directory. `--out` itself, and any of its
  parent directories, may not exist yet at the time the tool is invoked — the
  tool must create the entire directory chain as needed (the same way a
  recursive "make directories" operation would, not a single-level directory
  creation that assumes its parent already exists). The tool must create a
  `derivatives` subdirectory under `<out>` (i.e. `<out>/derivatives/`)
  containing every output derivative file, and must write `manifest.json`
  directly under `<out>` (i.e. `<out>/manifest.json`), not under the
  `derivatives` subdirectory.

In this environment, the tool is invoked as:

    /app/build/derive --sources /app/assets/src \
                       --csv /app/assets/src/manifest_inputs.csv \
                       --spec /app/spec/asset_processing_spec.md \
                       --out /app/out

which must produce derivative files under `/app/out/derivatives/` and a
manifest at `/app/out/manifest.json`.

**Rule IF-001:** On success, the tool must exit with status code 0.

**Rule IF-002:** On any unrecoverable error (a required flag missing, a
referenced path not found, a classification row referencing an asset class
this specification does not define), the tool must exit with a non-zero
status code and must not leave a partially-written `manifest.json` in place —
either the manifest reflects a fully successful run, or it is not written at
all.

**Rule IF-003:** The tool must never write to, modify, delete, or move any
file under `--sources`'s directory tree, including the classification CSV
itself. All output is confined to `--out`'s directory tree.

**Rule IF-004:** Running the tool a second time with the same flags against
the same, unmodified `--sources` and `--csv` inputs must be safe to do (must
not error because output already exists) and must produce the byte-identical
result required by Section 12.
---

## 17. Validation Rule Reference

The following table cross-references every numbered rule in this document by
the section that defines it, for quick lookup. This table is a reference
index only — the authoritative definition of each rule is the prose in its
originating section, not this table; do not attempt to implement a rule from
its one-line summary alone.

| Rule ID | Section | One-line summary |
|---|---|---|
| OR-001 | 2 | Orientation normalization runs before geometry selection |
| OR-002 | 2 | Swap width/height for orientation values in {5,6,7,8} |
| OR-003 | 2 | Output must not carry a non-trivial orientation tag |
| CL-001 | 3 | Every CSV row produces exactly one derivative |
| CL-002 | 3 | No derivatives for files absent from the CSV |
| CL-003 | 3 | Filenames are opaque byte sequences; handle high-bit bytes safely |
| CL-004 | 3 | Fail loudly on an unrecognized asset class name |
| TH-001 | 4 | thumbnail output is exactly 320x320 |
| TH-002 | 4 | thumbnail scale factor per Section 9.1, crop per Section 10 |
| CD-001 | 5 | card output is exactly 640x400 |
| CD-002 | 5 | card computes excess generally on both axes |
| AV-001 | 6 | avatar output is exactly 200x200 |
| AV-002 | 6 | avatar shares cover-mode formulas with thumbnail/card |
| HR-001 | 7 | hero scale factor uses the 1920x1080 box |
| HR-002 | 7 | hero clamps scale factor to 1.0 (shrink-only) |
| HR-003 | 7 | hero never letterboxes/pads |
| BN-001 | 8 | banner scale factor uses the 1200x300 box, no clamp |
| BN-002 | 8 | banner never letterboxes/pads |
| RD-001 | 9.3 | floor-with-tie applied independently per axis |
| RD-002 | 9.3 | tie detection uses exact arithmetic, not float equality |
| CR-001 | 10 | crop offset is floor(excess/2) per axis |
| CR-002 | 10 | crop rectangle is exactly target size at (left, top) |
| IC-001 | 11 | preserve embedded profile bytes exactly, if present |
| IC-002 | 11 | embed canonical sRGB.icc if source has no profile |
| IC-003 | 11 | stripping all metadata is forbidden |
| IC-004 | 11 | no colorspace/gamut conversion of pixel values |
| DT-001 | 12 | two runs produce byte-identical derivative files |
| DT-002 | 12 | two runs produce byte-identical manifest.json |
| DT-003 | 12 | no embedded timestamps in output files |
| PC-001 | 13 | already-conformant sources are copied byte-for-byte |
| PC-002 | 13 | conformance requires geometry + orientation + profile all satisfied |
| PC-003 | 13 | passthrough still gets a normal manifest entry and ordering position |
| NM-001 | 14 | four-step byte transform for the filename stem |
| NM-002 | 14 | collapse/strip hyphens in the transformed stem |
| NM-003 | 14 | final filename template |
| MF-001 | 15 | one manifest entry per CSV row |
| MF-002 | 15 | required fields, exact key names and JSON types |
| MF-003 | 15 | sort by (asset_class, transformed_stem), not filesystem order |
| MF-004 | 15 | manifest is valid, reproducible JSON |
| IF-001 | 16 | exit 0 on success |
| IF-002 | 16 | exit non-zero and write no manifest on failure |
| IF-003 | 16 | never modify anything under --sources |
| IF-004 | 16 | safe and byte-identical to re-run |
---

## 18. Terminology and Style Conventions Used in This Document

A short note on conventions used throughout this specification, provided so
that phrasing choices are not mistaken for meaningful technical distinctions
where none is intended.

The word "must" is used throughout for a hard requirement this pipeline's
verification checks directly; "should" is used for a strong recommendation
that is not itself directly checked (for example, logging verbosity, or
internal code organization); "may" indicates something explicitly permitted
but not required (for example, parallelizing across source files).

Numbered rules (`Rule XX-NNN`) are the specific, checkable requirements this
document defines; the surrounding prose in each section provides rationale
and worked context for those rules but a rule's own statement, not the
surrounding prose, is the precise boundary of what it requires. Where prose
and a numbered rule appear to describe the same requirement in
slightly different words, the numbered rule's wording is authoritative.

Pixel dimensions are always given as width-by-height (never height-by-width)
throughout this document, matching the `WxH` convention used in the naming
template (Section 14) and in common image-tooling command-line conventions
generally.

Section cross-references (for example, "see Section 9.1") refer to sections
of this same document; references to "Appendix" refer to the lettered
appendices following this section; references to a specific "Rule" refer to
the numbered rules catalogued in the Validation Rule Reference (Section 17).
---

## Appendix D: Glossary

**Asset class.** One of the five named categories (`thumbnail`, `card`,
`avatar`, `hero`, `banner`) a source is assigned to via the classification
CSV. Each asset class has its own target geometry and mode (cover or fit).

**Bounding box.** For a fit class, the maximum width and height the scaled
output is allowed to occupy. The scaled output touches at least one edge of
the bounding box and never exceeds it on either axis; it is not padded out to
the box's exact dimensions.

**Byte-for-byte identical.** Two files whose raw bytes match exactly,
position for position, with no differences at all — a stronger condition
than "renders as the same image" or "has the same dimensions," which this
specification uses precisely because pixel-level or metadata-level equality
is not sufficient for the determinism and passthrough requirements in
Sections 12 and 13.

**Canonical sRGB profile.** The specific ICC profile file shipped at
`/app/assets/color_profiles/sRGB.icc` in this environment, used verbatim
whenever Section 11 calls for embedding an assumed sRGB profile. "Canonical"
here means "the one, specific file this pipeline uses," not "the industry
standard sRGB profile" in the abstract — many bit-for-bit different ICC
profiles all validly describe the sRGB color space, and this pipeline's
correctness requirement is byte-equality against this specific shipped file,
not merely "some sRGB profile or other."

**Classification CSV.** The `manifest_inputs.csv` file mapping source
filenames to asset class names, described in Section 3.

**Cover mode.** The scaling mode used by `thumbnail`, `card`, and `avatar`,
in which the source is scaled so that it fully covers a fixed target
rectangle on both axes and the overhanging excess is cropped away. Contrast
with fit mode.

**Derivative.** An output image file produced by this pipeline from a single
source image, per the rules for that source's asset class.

**EXIF orientation tag.** A standard metadata field (tag number `0x0112`)
some image formats carry, indicating how a viewer should rotate and/or mirror
the stored raster to display it correctly. See Section 2 for the full list
of values this pipeline must handle.

**Fit mode.** The scaling mode used by `hero` and `banner`, in which the
source is scaled, preserving aspect ratio, to fit entirely within a bounding
box, with no cropping and no letterbox padding. Contrast with cover mode.

**Floor-with-tie.** This pipeline's rounding convention for non-integer
scaled dimensions, defined in Section 9.3: floor in general, except that an
exact `.5` fractional remainder rounds up rather than down.

**ICC profile.** A binary color profile, conforming to the ICC (International
Color Consortium) profile format, embedded in an image file to describe how
its stored pixel values map to real-world color. See Section 11 for this
pipeline's policy on when a profile is preserved versus assumed and embedded.

**Idempotent / idempotency.** In this document, the property that running the
pipeline a second time against unchanged inputs produces exactly the same
output bytes as the first run — not merely equivalent-looking output, but
byte-identical output, including the manifest.

**Manifest.** The `manifest.json` file summarizing every derivative produced
by a single pipeline run, per the schema in Section 15.

**Orientation-normalized dimensions.** A source's width and height *after*
Section 2's orientation normalization has been applied — the dimensions that
must be used for every geometry decision elsewhere in this document, as
opposed to the source's raw, stored (pre-rotation) raster dimensions.

**Passthrough.** Informal term for the already-conformant source handling
defined in Section 13: copying a source's bytes to its output location
unchanged instead of re-encoding it.

**Shrink-only.** A restriction, applying to the `hero` asset class only,
that forbids upscaling: if the computed fit-mode scale factor would enlarge
the source, it is clamped to 1.0 instead (Rule HR-002).

**Source (source image / source asset).** A single vendor-submitted image
file under the source asset directory, referenced by exactly one row of the
classification CSV.

**Stem (filename stem).** A filename with its extension and the final `.`
separator removed. The naming template (Section 14) transforms a source's
stem, not its full filename, when constructing an output filename.

**Target dimensions.** For a cover class, the fixed exact pixel width and
height every derivative in that class must have, regardless of the source's
own aspect ratio.

**Transformed stem.** The result of applying Section 14's byte-by-byte
transformation algorithm to a source's filename stem; used both as a
component of the output filename and as the secondary sort key for the
manifest's deterministic ordering (Rule MF-003).
### Additional Terms

**Alpha channel.** A per-pixel transparency value some image formats can
carry alongside color data. Not exercised by any source in this
environment's shipped fixture set.

**Bounding box aspect ratio.** The ratio of a fit class's box width to its
box height (for example, `hero`'s 1920:1080 simplifies to 16:9). Referenced
informally in several sections; the pipeline's actual computation never
needs to simplify or compare aspect ratios as fractions directly, since the
scale-factor formula (Section 9.2) operates on the box's width and height
values directly.

**Chroma subsampling.** A JPEG encoding parameter controlling how much color
(as opposed to luminance) detail is discarded during compression. Section 12
requires this be held fixed across runs but does not mandate a specific
subsampling scheme beyond "whatever keeps two runs byte-identical."

**Classification lookup.** The act of looking up a source's filename in the
classification CSV to determine its asset class (Section 3).

**Cover-mode excess.** The amount, in pixels, by which a cover-mode scaled
image exceeds its target on a given axis, before cropping (Section 10).

**CRC / checksum (not used by this pipeline).** Some other Terminus media
pipelines use a CRC or similar checksum for quick integrity checks; this
pipeline uses SHA-256 exclusively (Section 15) and has no CRC requirement of
its own.

**DCT method.** A JPEG encoding parameter affecting the discrete cosine
transform implementation used during compression. Referenced in Section 12's
determinism discussion as one of several encoder parameters that must be
held fixed, alongside quality and chroma subsampling.

**Decode-transform-encode.** Informal shorthand, used in Section 13,
for the general (non-passthrough) processing path: decoding a
source's pixels, applying orientation/geometry/color transforms, and
re-encoding the result.

**Derivative filename.** See "Transformed stem" and Section 14; the full,
final filename of an output derivative file.

**Downstream consumer.** Any system that reads this pipeline's output
(derivative files or the manifest) after a pipeline run completes.

**Encoder.** The software component (in practice, ImageMagick's JPEG, PNG,
or TIFF write path) responsible for compressing final pixel data to an
output file.

**Excess (cover mode).** See "Cover-mode excess."

**Fixture set.** Informal term for the specific set of source image files and
their classification CSV shipped in this environment's `/app/assets/src/`
directory.

**Fragment / fragmentation (not applicable).** Some other Terminus storage
formats support fragmented/non-contiguous record storage; this concept has
no analogue in this pipeline, which processes whole, complete source image
files only.

**Geometry decision.** Any computation that depends on a source's width
and/or height — scale factor selection, rounding, crop rectangle placement.
Section 2's ordering rule (Rule OR-001) requires orientation normalization
to precede every geometry decision.

**Idempotent rebuild.** A pipeline invocation performed against inputs
identical to a previous invocation's inputs, expected to produce
byte-identical output (Section 12, Rule IF-004).

**Ingestion.** Informal term for the process of a source file and its
classification row entering the pipeline's processing scope; not a
formally defined pipeline stage of its own beyond the classification lookup
(Section 3).

**Lanczos filter.** The specific resampling filter this pipeline
standardizes on for every resize operation (Section 12), chosen for its
generally favorable sharpness/ringing tradeoff relative to simpler filters,
independent of any property specific to this pipeline's asset classes.

**Lookup table (naming context).** A fixed-size array some implementations
use to classify or transform bytes during the naming template's byte-by-byte
pass (Section 14).

**Multi-byte UTF-8 sequence.** A single Unicode code point encoded as more
than one byte in UTF-8; every byte in such a sequence, other than possibly
the first, has its high bit set. Section 14's naming template preserves
these sequences byte-for-byte rather than attempting to decode and
case-fold them.

**Non-contiguous storage (not applicable).** See "Fragment /
fragmentation."

**Passthrough source.** See "Passthrough" in the main glossary (Appendix D);
a source qualifying for Section 13's byte-identical copy behavior.

**Pixel buffer.** The decoded, in-memory representation of an image's pixel
data, prior to any re-encoding. Orientation normalization (Section 2)
operates on this representation.

**Product-design constant.** Informal term for a target
or bounding-box dimension (such as `card`'s 640x400) whose specific value
reflects a UI/product decision external to this pipeline's own logic, rather
than being derived from any property of vendor-submitted imagery.

**Rendering intent.** A field within an ICC profile's header describing how
out-of-gamut colors should be mapped during rendering. It must not be
treated as insignificant when checking exact profile-byte preservation
(Rule IC-001) — see Appendix U.

**Sort key.** The `(asset_class, transformed_stem)` tuple used to order the
manifest's `derivatives` array (Rule MF-003).

**Storefront.** The customer-facing web and mobile shopping surfaces that
consume `thumbnail` and `card` derivatives.

**Tie (rounding context).** A scaled dimension whose fractional remainder
is exactly `0.5`; see Section 9.3 and "Floor-with-tie" in the main glossary.

**Vendor drop / vendor batch.** A single delivery of source images and a
corresponding classification spreadsheet from an external vendor or agency,
converted by the vendor integrations team into this pipeline's
`manifest_inputs.csv` format.

**Wide-gamut display.** A display capable of reproducing a color gamut
wider than sRGB; referenced in Section 11's rationale for why untagged
sources must be explicitly tagged as sRGB rather than left without any
embedded profile at all.
---

## Appendix S: Field-by-Field Manifest Validation Notes

This appendix expands on Section 15's manifest schema with additional
per-field notes gathered from questions the vendor integrations team and the
cataloguing service's own maintainers have asked over this specification's
revision history. It does not add new fields or change any type or ordering
requirement already defined in Section 15.

**On `source_file`:** this field is the classification CSV's `filename`
value verbatim, not a path and not a case-normalized or otherwise cleaned-up
version of it. Two manifest entries can legitimately have very similar
`source_file` values differing only by case or by a single punctuation byte,
if the classification CSV itself contained two such distinct rows; the
manifest does not deduplicate or normalize this field in any way.

**On `asset_class`:** always one of the five lowercase class name strings;
this field is never capitalized, abbreviated, or pluralized differently than
how the classification CSV itself spells it, and the classification CSV in
this environment always uses the exact five lowercase spellings defined in
Sections 4 through 8.

**On `output_file`:** callers combining this field with the output
directory to locate the actual derivative file on disk should join it under
`<out>/derivatives/`, per Section 16 — this field itself never includes that
directory prefix, a leading slash, or any path separator beyond what might
incidentally appear in a source's own transformed stem (which, per Section
14's transformation rules, cannot happen, since path separator characters
like `/` are not in the preserved ASCII ranges of steps 1-2 and are not
high-bit bytes, so they always fall through to step 4's hyphen
substitution).

**On `width` and `height`:** always the derivative's actual final pixel
dimensions as written to disk, never the source's original dimensions,
never a bounding box or target constant restated regardless of what the
specific source actually produced (this distinction matters most for fit
classes, where different sources of the same class legitimately produce
different `width`/`height` values from each other).

**On `icc_policy`:** exactly one of the two literal strings defined in
Section 15; no third value (for example, a hypothetical `"none"` for a
derivative with no profile at all) is valid, because Section 11's policy
never produces a profile-less output — every derivative has an embedded
profile one way or the other (Rule IC-001 or Rule IC-002), so `icc_policy`
always describes which of those two rules applied, never an absence of
either.

**On `orientation_normalized`:** a JSON boolean reflecting whether the
*source's* original tag required a rotation, not whether the *output*
happens to carry a tag (per Rule OR-003, the output never carries a
non-trivial tag regardless of this field's value). This field is a record
of what happened during processing, not a description of the output file's
own remaining metadata state.

**On `sha256`:** always lowercase hexadecimal, 64 characters, computed over
the exact final on-disk bytes. Two different
derivatives (different `output_file` values) could in principle have the
same `sha256` value if their bytes happened to be identical — this is not
checked or prevented by this specification, since it is not itself an error
condition, merely a coincidence that could occur if, for example, two
different sources happened to produce byte-identical output through
unrelated code paths (this is not expected to occur in this environment's
fixture set, but is not forbidden in general).
---

## Appendix U: ICC Profile Byte Structure Notes

This appendix gives a brief, practical description of the ICC profile
format for implementers who have not worked with embedded color profiles
directly before. It is background information supporting Section 11's
byte-exact preservation requirement (Rule IC-001) and is not itself a
processing rule.

An ICC profile begins with a fixed-size, 128-byte header. Among the header's
fields (each a fixed-width, big-endian binary value at a fixed byte offset)
are the total profile size, the profile/device class, the color space the
profile describes, the profile connection space, the profile creation date,
the signature identifying the file as an ICC profile, and a rendering intent
field. Following the header is a tag table: a count of tags, followed by
one directory entry per tag giving that tag's signature, its byte offset
within the file, and its byte length; the actual tag data follows the tag
table, referenced by those offsets.

The practical implication for this specification is that "the same profile"
is not a fuzzy, semantic notion — it is a specific, finite sequence of
bytes, and Rule IC-001's preservation requirement means literally
retransmitting that exact sequence of bytes into the output file, not
regenerating an equivalent profile from parsed field values, and not
re-serializing a profile that has been parsed into some in-memory
representation and written back out (which, depending on the library used,
can reorder tags, re-align tag data, or otherwise produce a different, if
functionally equivalent, byte sequence than the original file).

This matters because the rendering intent lives in the profile's
fixed-offset header rather than in the tag table, so it is easy for an
implementation that treats "the profile" as "the tag table's color
transform data" to overlook the header fields (rendering intent among them)
as not really part of "the profile" in the sense that matters — but Rule
IC-001 draws no such distinction: the entire byte sequence, header and tag
table together, must match exactly.

Embedding a profile (Rule IC-002's canonical-sRGB case) is more
straightforward: this is simply writing the canonical file's exact bytes
into the appropriate profile-carrying location for the output container
format (a JPEG APP2 marker segment, a PNG `iCCP` chunk, or a TIFF ICC
profile tag, depending on which of the three output container formats
applies), which general-purpose image libraries typically expose as a
single "embed this profile" operation without requiring the implementer to
construct any of these container-specific encodings by hand.
---

## Closing Note

This concludes the Terminus Media Engineering Asset Processing Specification,
revision 6.3.0. This document's numbered sections (1 through 18, excluding
the appendices) constitute the complete, authoritative set of processing
requirements; the appendices are supporting material intended to make those
requirements easier to apply correctly, not an additional, separate source of
requirements in their own right.
