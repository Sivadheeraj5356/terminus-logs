# Observatory Operations Notebook — SPECZ Spool and Calibration

Maintained by the spectrograph operations group. Entries are chronological.
Superseded policies are marked explicitly; do not apply obsolete rules.

## 2019-03-01 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0000. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2018-11-01 is retired; use this entry for current operations.

OBSOLETE (superseded 2021-06-14): payloads are big-endian 12-bit groups. Do not use for revision 2 frames.

## 2019-03-10 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0001. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2018-11-10 is retired; use this entry
for current operations.

## 2019-03-19 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0002. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2018-11-19 is retired; use this entry for current
operations.

## 2019-03-28 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0003. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2018-11-28 is retired; use this entry for current
operations.

## 2019-04-06 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0004. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2018-12-07 is retired; use this entry for current
operations.

## 2019-04-15 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0005. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2018-12-16 is retired; use this entry
for current operations.

## 2019-04-24 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0006. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2018-12-25 is retired; use this entry for current
operations.

## 2019-05-03 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0007. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-01-03 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2019-05-12 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0008. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2019-01-12 is retired; use this entry
for current operations.

## 2019-05-21 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0009. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2019-01-21 is retired; use this entry for current operations.

## 2019-05-30 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0010. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2019-01-30 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2019-06-08 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0011. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-02-08 is retired; use this entry for current
operations.

## 2019-06-17 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0012. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-02-17 is retired; use this entry for current
operations.

## 2019-06-26 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0013. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-02-26 is retired; use this entry for current
operations.

## 2019-07-05 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0014. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2019-03-07 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2019-07-14 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0015. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2019-03-16 is retired; use
this entry for current operations.

## 2019-07-23 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0016. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2019-03-25 is retired; use this entry
for current operations.

## 2019-08-01 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0017. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-04-03 is retired; use this entry for current
operations.

## 2019-08-10 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0018. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2019-04-12 is retired; use
this entry for current operations.

## 2019-08-19 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0019. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2019-04-21 is retired; use
this entry for current operations.

## 2019-08-28 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0020. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2019-04-30 is retired; use this entry for current operations.

## 2019-09-06 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0021. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2019-05-09 is retired; use this entry
for current operations.

## 2019-09-15 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0022. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-05-18 is retired; use this entry for current
operations.

## 2019-09-24 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0023. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-05-27 is retired; use this entry for current
operations.

## 2019-10-03 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0024. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-06-05 is retired; use this entry for current
operations.

## 2019-10-12 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0025. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2019-06-14 is retired; use this entry
for current operations.

## 2019-10-21 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0026. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-06-23 is retired; use this entry for current
operations.

## 2019-10-30 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0027. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-07-02 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2019-11-08 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0028. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2019-07-11 is retired; use this entry
for current operations.

## 2019-11-17 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0029. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2019-07-20 is retired; use this entry for current operations.

## 2019-11-26 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0030. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2019-07-29 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2019-12-05 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0031. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-08-07 is retired; use this entry for current
operations.

## 2019-12-14 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0032. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-08-16 is retired; use this entry for current
operations.

## 2019-12-23 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0033. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-08-25 is retired; use this entry for current
operations.

## 2020-01-01 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0034. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2019-09-03 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2020-01-10 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0035. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2019-09-12 is retired; use
this entry for current operations.

## 2020-01-19 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0036. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2019-09-21 is retired; use this entry
for current operations.

## 2020-01-28 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0037. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-09-30 is retired; use this entry for current
operations.

## 2020-02-06 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0038. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2019-10-09 is retired; use
this entry for current operations.

## 2020-02-15 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0039. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2019-10-18 is retired; use
this entry for current operations.

## 2020-02-24 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0040. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2019-10-27 is retired; use this entry for current operations.

## 2020-03-04 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0041. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2019-11-05 is retired; use this entry
for current operations.

## 2020-03-13 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0042. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-11-14 is retired; use this entry for current
operations.

## 2020-03-22 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0043. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-11-23 is retired; use this entry for current
operations.

## 2020-03-31 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0044. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-12-02 is retired; use this entry for current
operations.

## 2020-04-09 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0045. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2019-12-11 is retired; use this entry
for current operations.

## 2020-04-18 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0046. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-12-20 is retired; use this entry for current
operations.

## 2020-04-27 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0047. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2019-12-29 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2020-05-06 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0048. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2020-01-07 is retired; use this entry
for current operations.

## 2020-05-15 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0049. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2020-01-16 is retired; use this entry for current operations.

## 2020-05-24 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0050. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2020-01-25 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2020-06-02 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0051. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-02-03 is retired; use this entry for current
operations.

## 2020-06-11 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0052. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-02-12 is retired; use this entry for current
operations.

## 2020-06-20 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0053. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-02-21 is retired; use this entry for current
operations.

## 2020-06-29 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0054. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2020-03-01 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2020-07-08 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0055. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2020-03-10 is retired; use
this entry for current operations.

## 2020-07-17 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0056. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2020-03-19 is retired; use this entry
for current operations.

## 2020-07-26 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0057. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-03-28 is retired; use this entry for current
operations.

## 2020-08-04 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0058. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2020-04-06 is retired; use
this entry for current operations.

## 2020-08-13 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0059. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2020-04-15 is retired; use
this entry for current operations.

## 2020-08-22 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0060. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2020-04-24 is retired; use this entry for current operations.

## 2020-08-31 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0061. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2020-05-03 is retired; use this entry
for current operations.

## 2020-09-09 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0062. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-05-12 is retired; use this entry for current
operations.

## 2020-09-18 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0063. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-05-21 is retired; use this entry for current
operations.

## 2020-09-27 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0064. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-05-30 is retired; use this entry for current
operations.

## 2020-10-06 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0065. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2020-06-08 is retired; use this entry
for current operations.

## 2020-10-15 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0066. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-06-17 is retired; use this entry for current
operations.

## 2020-10-24 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0067. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-06-26 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2020-11-02 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0068. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2020-07-05 is retired; use this entry
for current operations.

## 2020-11-11 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0069. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2020-07-14 is retired; use this entry for current operations.

## 2020-11-20 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0070. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2020-07-23 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2020-11-29 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0071. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-08-01 is retired; use this entry for current
operations.

## 2020-12-08 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0072. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-08-10 is retired; use this entry for current
operations.

## 2020-12-17 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0073. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-08-19 is retired; use this entry for current
operations.

## 2020-12-26 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0074. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2020-08-28 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2021-01-04 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0075. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2020-09-06 is retired; use
this entry for current operations.

## 2021-01-13 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0076. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2020-09-15 is retired; use this entry
for current operations.

## 2021-01-22 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0077. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-09-24 is retired; use this entry for current
operations.

## 2021-01-31 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0078. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2020-10-03 is retired; use
this entry for current operations.

## 2021-02-09 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0079. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2020-10-12 is retired; use
this entry for current operations.

## 2021-02-18 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0080. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2020-10-21 is retired; use this entry for current operations.

## 2021-02-27 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0081. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2020-10-30 is retired; use this entry
for current operations.

## 2021-03-08 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0082. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-11-08 is retired; use this entry for current
operations.

## 2021-03-17 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0083. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-11-17 is retired; use this entry for current
operations.

## 2021-03-26 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0084. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-11-26 is retired; use this entry for current
operations.

## 2021-04-04 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0085. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2020-12-05 is retired; use this entry
for current operations.

## 2021-04-13 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0086. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-12-14 is retired; use this entry for current
operations.

## 2021-04-22 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0087. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2020-12-23 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2021-05-01 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0088. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-01-01 is retired; use this entry
for current operations.

## 2021-05-10 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0089. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2021-01-10 is retired; use this entry for current operations.

## 2021-05-19 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0090. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2021-01-19 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2021-05-28 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0091. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-01-28 is retired; use this entry for current
operations.

## 2021-06-06 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0092. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-02-06 is retired; use this entry for current
operations.

## 2021-06-15 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0093. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-02-15 is retired; use this entry for current
operations.

## 2021-06-24 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0094. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2021-02-24 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2021-07-03 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0095. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2021-03-05 is retired; use
this entry for current operations.

## 2021-07-12 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0096. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-03-14 is retired; use this entry
for current operations.

## 2021-07-21 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0097. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-03-23 is retired; use this entry for current
operations.

## 2021-07-30 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0098. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2021-04-01 is retired; use
this entry for current operations.

## 2021-08-08 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0099. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2021-04-10 is retired; use
this entry for current operations.

## 2021-08-17 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0100. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2021-04-19 is retired; use this entry for current operations.

## 2021-08-26 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0101. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-04-28 is retired; use this entry
for current operations.

## 2021-09-04 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0102. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-05-07 is retired; use this entry for current
operations.

## 2021-09-13 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0103. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-05-16 is retired; use this entry for current
operations.

## 2021-09-22 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0104. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-05-25 is retired; use this entry for current
operations.

## 2021-10-01 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0105. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-06-03 is retired; use this entry
for current operations.

## 2021-10-10 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0106. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-06-12 is retired; use this entry for current
operations.

## 2021-10-19 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0107. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-06-21 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2021-10-28 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0108. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-06-30 is retired; use this entry
for current operations.

## 2021-11-06 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0109. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2021-07-09 is retired; use this entry for current operations.

## 2021-11-15 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0110. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2021-07-18 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2021-11-24 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0111. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-07-27 is retired; use this entry for current
operations.

## 2021-12-03 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0112. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-08-05 is retired; use this entry for current
operations.

## 2021-12-12 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0113. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-08-14 is retired; use this entry for current
operations.

## 2021-12-21 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0114. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2021-08-23 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2021-12-30 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0115. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2021-09-01 is retired; use
this entry for current operations.

## 2022-01-08 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0116. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-09-10 is retired; use this entry
for current operations.

## 2022-01-17 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0117. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-09-19 is retired; use this entry for current
operations.

## 2022-01-26 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0118. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2021-09-28 is retired; use
this entry for current operations.

## 2022-02-04 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0119. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2021-10-07 is retired; use
this entry for current operations.

## 2022-02-13 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0120. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2021-10-16 is retired; use this entry for current operations.

## 2022-02-22 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0121. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-10-25 is retired; use this entry
for current operations.

## 2022-03-03 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0122. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-11-03 is retired; use this entry for current
operations.

## 2022-03-12 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0123. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-11-12 is retired; use this entry for current
operations.

## 2022-03-21 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0124. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-11-21 is retired; use this entry for current
operations.

## 2022-03-30 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0125. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-11-30 is retired; use this entry
for current operations.

## 2022-04-08 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0126. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-12-09 is retired; use this entry for current
operations.

## 2022-04-17 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0127. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2021-12-18 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2022-04-26 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0128. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2021-12-27 is retired; use this entry
for current operations.

## 2022-05-05 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0129. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2022-01-05 is retired; use this entry for current operations.

## 2022-05-14 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0130. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2022-01-14 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2022-05-23 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0131. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-01-23 is retired; use this entry for current
operations.

## 2022-06-01 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0132. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-02-01 is retired; use this entry for current
operations.

## 2022-06-10 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0133. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-02-10 is retired; use this entry for current
operations.

## 2022-06-19 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0134. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2022-02-19 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2022-06-28 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0135. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2022-02-28 is retired; use
this entry for current operations.

## 2022-07-07 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0136. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2022-03-09 is retired; use this entry
for current operations.

## 2022-07-16 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0137. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-03-18 is retired; use this entry for current
operations.

## 2022-07-25 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0138. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2022-03-27 is retired; use
this entry for current operations.

## 2022-08-03 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0139. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2022-04-05 is retired; use
this entry for current operations.

## 2022-08-12 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0140. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2022-04-14 is retired; use this entry for current operations.

## 2022-08-21 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0141. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2022-04-23 is retired; use this entry
for current operations.

## 2022-08-30 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0142. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-05-02 is retired; use this entry for current
operations.

## 2022-09-08 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0143. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-05-11 is retired; use this entry for current
operations.

## 2022-09-17 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0144. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-05-20 is retired; use this entry for current
operations.

## 2022-09-26 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0145. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2022-05-29 is retired; use this entry
for current operations.

## 2022-10-05 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0146. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-06-07 is retired; use this entry for current
operations.

## 2022-10-14 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0147. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-06-16 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2022-10-23 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0148. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2022-06-25 is retired; use this entry
for current operations.

## 2022-11-01 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0149. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2022-07-04 is retired; use this entry for current operations.

## 2022-11-10 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0150. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2022-07-13 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2022-11-19 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0151. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-07-22 is retired; use this entry for current
operations.

## 2022-11-28 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0152. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-07-31 is retired; use this entry for current
operations.

## 2022-12-07 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0153. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-08-09 is retired; use this entry for current
operations.

## 2022-12-16 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0154. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2022-08-18 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2022-12-25 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0155. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2022-08-27 is retired; use
this entry for current operations.

## 2023-01-03 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0156. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2022-09-05 is retired; use this entry
for current operations.

## 2023-01-12 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0157. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-09-14 is retired; use this entry for current
operations.

## 2023-01-21 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0158. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2022-09-23 is retired; use
this entry for current operations.

## 2023-01-30 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0159. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2022-10-02 is retired; use
this entry for current operations.

## 2023-02-08 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0160. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2022-10-11 is retired; use this entry for current operations.

## 2023-02-17 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0161. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2022-10-20 is retired; use this entry
for current operations.

## 2023-02-26 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0162. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-10-29 is retired; use this entry for current
operations.

## 2023-03-07 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0163. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-11-07 is retired; use this entry for current
operations.

## 2023-03-16 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0164. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-11-16 is retired; use this entry for current
operations.

## 2023-03-25 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0165. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2022-11-25 is retired; use this entry
for current operations.

## 2023-04-03 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0166. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-12-04 is retired; use this entry for current
operations.

## 2023-04-12 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0167. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2022-12-13 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2023-04-21 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0168. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2022-12-22 is retired; use this entry
for current operations.

## 2023-04-30 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0169. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2022-12-31 is retired; use this entry for current operations.

## 2023-05-09 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0170. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2023-01-09 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2023-05-18 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0171. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-01-18 is retired; use this entry for current
operations.

## 2023-05-27 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0172. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-01-27 is retired; use this entry for current
operations.

## 2023-06-05 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0173. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-02-05 is retired; use this entry for current
operations.

## 2023-06-14 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0174. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2023-02-14 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2023-06-23 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0175. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2023-02-23 is retired; use
this entry for current operations.

## 2023-07-02 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0176. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2023-03-04 is retired; use this entry
for current operations.

## 2023-07-11 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0177. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-03-13 is retired; use this entry for current
operations.

## 2023-07-20 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0178. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2023-03-22 is retired; use
this entry for current operations.

## 2023-07-29 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0179. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2023-03-31 is retired; use
this entry for current operations.

## 2023-08-07 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0180. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2023-04-09 is retired; use this entry for current operations.

## 2023-08-16 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0181. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2023-04-18 is retired; use this entry
for current operations.

## 2023-08-25 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0182. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-04-27 is retired; use this entry for current
operations.

## 2023-09-03 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0183. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-05-06 is retired; use this entry for current
operations.

## 2023-09-12 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0184. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-05-15 is retired; use this entry for current
operations.

## 2023-09-21 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0185. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2023-05-24 is retired; use this entry
for current operations.

## 2023-09-30 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0186. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-06-02 is retired; use this entry for current
operations.

## 2023-10-09 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0187. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-06-11 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2023-10-18 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0188. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2023-06-20 is retired; use this entry
for current operations.

## 2023-10-27 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0189. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2023-06-29 is retired; use this entry for current operations.

## 2023-11-05 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0190. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2023-07-08 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2023-11-14 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0191. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-07-17 is retired; use this entry for current
operations.

## 2023-11-23 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0192. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-07-26 is retired; use this entry for current
operations.

## 2023-12-02 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0193. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-08-04 is retired; use this entry for current
operations.

## 2023-12-11 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0194. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2023-08-13 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2023-12-20 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0195. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2023-08-22 is retired; use
this entry for current operations.

## 2023-12-29 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0196. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2023-08-31 is retired; use this entry
for current operations.

## 2024-01-07 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0197. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-09-09 is retired; use this entry for current
operations.

## 2024-01-16 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0198. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2023-09-18 is retired; use
this entry for current operations.

## 2024-01-25 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0199. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2023-09-27 is retired; use
this entry for current operations.

## 2024-02-03 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0200. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2023-10-06 is retired; use this entry for current operations.

## 2024-02-12 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0201. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2023-10-15 is retired; use this entry
for current operations.

## 2024-02-21 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0202. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-10-24 is retired; use this entry for current
operations.

## 2024-03-01 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0203. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-11-02 is retired; use this entry for current
operations.

## 2024-03-10 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0204. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-11-11 is retired; use this entry for current
operations.

## 2024-03-19 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0205. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2023-11-20 is retired; use this entry
for current operations.

## 2024-03-28 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0206. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-11-29 is retired; use this entry for current
operations.

## 2024-04-06 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0207. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2023-12-08 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2024-04-15 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0208. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2023-12-17 is retired; use this entry
for current operations.

## 2024-04-24 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0209. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2023-12-26 is retired; use this entry for current operations.

## 2024-05-03 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0210. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-01-04 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2024-05-12 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0211. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-01-13 is retired; use this entry for current
operations.

## 2024-05-21 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0212. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-01-22 is retired; use this entry for current
operations.

## 2024-05-30 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0213. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-01-31 is retired; use this entry for current
operations.

## 2024-06-08 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0214. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2024-02-09 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2024-06-17 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0215. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-02-18 is retired; use
this entry for current operations.

## 2024-06-26 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0216. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2024-02-27 is retired; use this entry
for current operations.

## 2024-07-05 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0217. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-03-07 is retired; use this entry for current
operations.

## 2024-07-14 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0218. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-03-16 is retired; use
this entry for current operations.

## 2024-07-23 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0219. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-03-25 is retired; use
this entry for current operations.

## 2024-08-01 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0220. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2024-04-03 is retired; use this entry for current operations.

## 2024-08-10 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0221. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2024-04-12 is retired; use this entry
for current operations.

## 2024-08-19 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0222. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-04-21 is retired; use this entry for current
operations.

## 2024-08-28 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0223. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-04-30 is retired; use this entry for current
operations.

## 2024-09-06 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0224. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-05-09 is retired; use this entry for current
operations.

## 2024-09-15 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0225. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2024-05-18 is retired; use this entry
for current operations.

## 2024-09-24 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0226. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-05-27 is retired; use this entry for current
operations.

## 2024-10-03 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0227. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-06-05 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2024-10-12 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0228. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2024-06-14 is retired; use this entry
for current operations.

## 2024-10-21 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0229. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2024-06-23 is retired; use this entry for current operations.

## 2024-10-30 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0230. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-07-02 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2024-11-08 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0231. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-07-11 is retired; use this entry for current
operations.

## 2024-11-17 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0232. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-07-20 is retired; use this entry for current
operations.

## 2024-11-26 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0233. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-07-29 is retired; use this entry for current
operations.

## 2024-12-05 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0234. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2024-08-07 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2024-12-14 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0235. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-08-16 is retired; use
this entry for current operations.

## 2024-12-23 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0236. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2024-08-25 is retired; use this entry
for current operations.

## 2025-01-01 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0237. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-09-03 is retired; use this entry for current
operations.

## 2025-01-10 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0238. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-09-12 is retired; use
this entry for current operations.

## 2025-01-19 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0239. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-09-21 is retired; use
this entry for current operations.

## 2025-01-28 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0240. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2024-09-30 is retired; use this entry for current operations.

## 2025-02-06 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0241. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2024-10-09 is retired; use this entry
for current operations.

## 2025-02-15 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0242. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-10-18 is retired; use this entry for current
operations.

## 2025-02-24 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0243. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-10-27 is retired; use this entry for current
operations.

## 2025-03-05 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0244. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-11-05 is retired; use this entry for current
operations.

## 2025-03-14 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0245. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2024-11-14 is retired; use this entry
for current operations.

## 2025-03-23 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0246. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-11-23 is retired; use this entry for current
operations.

## 2025-04-01 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0247. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2024-12-02 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2025-04-10 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0248. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2024-12-11 is retired; use this entry
for current operations.

## 2025-04-19 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0249. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2024-12-20 is retired; use this entry for current operations.

## 2025-04-28 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0250. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2024-12-29 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2025-05-07 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0251. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-01-07 is retired; use this entry for current
operations.

## 2025-05-16 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0252. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-01-16 is retired; use this entry for current
operations.

## 2025-05-25 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0253. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-01-25 is retired; use this entry for current
operations.

## 2025-06-03 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0254. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2025-02-03 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2025-06-12 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0255. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2025-02-12 is retired; use
this entry for current operations.

## 2025-06-21 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0256. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2025-02-21 is retired; use this entry
for current operations.

## 2025-06-30 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0257. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-03-02 is retired; use this entry for current
operations.

## 2025-07-09 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0258. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2025-03-11 is retired; use
this entry for current operations.

## 2025-07-18 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0259. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2025-03-20 is retired; use
this entry for current operations.

## 2025-07-27 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0260. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2025-03-29 is retired; use this entry for current operations.

## 2025-08-05 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0261. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2025-04-07 is retired; use this entry
for current operations.

## 2025-08-14 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0262. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-04-16 is retired; use this entry for current
operations.

## 2025-08-23 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0263. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-04-25 is retired; use this entry for current
operations.

## 2025-09-01 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0264. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-05-04 is retired; use this entry for current
operations.

## 2025-09-10 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0265. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2025-05-13 is retired; use this entry
for current operations.

## 2025-09-19 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0266. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-05-22 is retired; use this entry for current
operations.

## 2025-09-28 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0267. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-05-31 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2025-10-07 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0268. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2025-06-09 is retired; use this entry
for current operations.

## 2025-10-16 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0269. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2025-06-18 is retired; use this entry for current operations.

## 2025-10-25 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0270. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2025-06-27 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2025-11-03 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0271. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-07-06 is retired; use this entry for current
operations.

## 2025-11-12 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0272. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-07-15 is retired; use this entry for current
operations.

## 2025-11-21 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0273. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-07-24 is retired; use this entry for current
operations.

## 2025-11-30 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0274. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2025-08-02 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2025-12-09 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0275. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2025-08-11 is retired; use
this entry for current operations.

## 2025-12-18 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0276. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2025-08-20 is retired; use this entry
for current operations.

## 2025-12-27 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0277. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-08-29 is retired; use this entry for current
operations.

## 2026-01-05 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0278. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2025-09-07 is retired; use
this entry for current operations.

## 2026-01-14 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0279. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2025-09-16 is retired; use
this entry for current operations.

## 2026-01-23 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0280. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2025-09-25 is retired; use this entry for current operations.

## 2026-02-01 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0281. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2025-10-04 is retired; use this entry
for current operations.

## 2026-02-10 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0282. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-10-13 is retired; use this entry for current
operations.

## 2026-02-19 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0283. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-10-22 is retired; use this entry for current
operations.

## 2026-02-28 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0284. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-10-31 is retired; use this entry for current
operations.

## 2026-03-09 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0285. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2025-11-09 is retired; use this entry
for current operations.

## 2026-03-18 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0286. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-11-18 is retired; use this entry for current
operations.

## 2026-03-27 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0287. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2025-11-27 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2026-04-05 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0288. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2025-12-06 is retired; use this entry
for current operations.

## 2026-04-14 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0289. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2025-12-15 is retired; use this entry for current operations.

## 2026-04-23 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0290. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2025-12-24 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2026-05-02 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0291. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-01-02 is retired; use this entry for current
operations.

## 2026-05-11 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0292. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-01-11 is retired; use this entry for current
operations.

## 2026-05-20 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0293. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-01-20 is retired; use this entry for current
operations.

## 2026-05-29 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0294. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2026-01-29 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2026-06-07 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0295. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2026-02-07 is retired; use
this entry for current operations.

## 2026-06-16 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0296. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2026-02-16 is retired; use this entry
for current operations.

## 2026-06-25 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0297. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-02-25 is retired; use this entry for current
operations.

## 2026-07-04 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0298. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2026-03-06 is retired; use
this entry for current operations.

## 2026-07-13 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0299. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2026-03-15 is retired; use
this entry for current operations.

## 2026-07-22 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0300. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2026-03-24 is retired; use this entry for current operations.

## 2026-07-31 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0301. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2026-04-02 is retired; use this entry
for current operations.

## 2026-08-09 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0302. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-04-11 is retired; use this entry for current
operations.

## 2026-08-18 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0303. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-04-20 is retired; use this entry for current
operations.

## 2026-08-27 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0304. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-04-29 is retired; use this entry for current
operations.

## 2026-09-05 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0305. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2026-05-08 is retired; use this entry
for current operations.

## 2026-09-14 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0306. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-05-17 is retired; use this entry for current
operations.

## 2026-09-23 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0307. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-05-26 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2026-10-02 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0308. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2026-06-04 is retired; use this entry
for current operations.

## 2026-10-11 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0309. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2026-06-13 is retired; use this entry for current operations.

## 2026-10-20 — Baseline policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space.

Operator log baseline-slope-0310. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline
policy: fit sloping line on sidebands 0:31 and 224:255 in wavelength space. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2026-06-22 is retired; use
this entry for current operations.

Current rule: subtract ordinary least-squares baseline fit a+b*lambda using unmasked pixels in both sidebands before peak metrics.

## 2026-10-29 — Peak analysis uses weighted centroid in nm after baseline removal.

Operator log centroid-nm-0311. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When peak analysis
uses weighted centroid in nm after baseline removal. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-07-01 is retired; use this entry for current
operations.

## 2026-11-07 — Integrated intensity uses trapezoidal rule in wavelength coordinates.

Operator log trap-int-0312. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When integrated
intensity uses trapezoidal rule in wavelength coordinates. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-07-10 is retired; use this entry for current
operations.

## 2026-11-16 — Baseline noise is sample standard deviation (n-1) of sideband residuals.

Operator log noise-sample-0313. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When baseline noise
is sample standard deviation (n-1) of sideband residuals. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-07-19 is retired; use this entry for current
operations.

## 2026-11-25 — Recovery: result fragment committed before manifest entry.

Operator log commit-order-0314. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When recovery:
result fragment committed before manifest entry. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2026-07-28 is retired; use this entry for current operations.

Write /data/state/results/<sha256>.json atomically, then append manifest.tsv line. Rebuild /output/drift.jsonl from all manifest-linked fragments sorted by instrument, session, sequence.

## 2026-12-04 — Replay suppression keys on content SHA-256 and logical (instrument,session,sequence).

Operator log replay-keys-0315. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When replay
suppression keys on content sha-256 and logical (instrument,session,sequence). This
entry cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2026-08-06 is retired; use
this entry for current operations.

## 2026-12-13 — Final drift.jsonl is materialized view rebuilt from committed fragments.

Operator log output-materialize-0316. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When final
drift.jsonl is materialized view rebuilt from committed fragments. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2026-08-15 is retired; use this entry
for current operations.

## 2026-12-22 — Site config may override reference wavelength and analysis windows only.

Operator log site-override-0317. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When site config may
override reference wavelength and analysis windows only. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-08-24 is retired; use this entry for current
operations.

## 2026-12-31 — Config precedence: environment path overrides, then site.conf, then defaults.conf.

Operator log config-precedence-0318. During shift review we verified acquisition
metadata, detector temperature logs, and spool lifecycle counters. The active build
label org.obs.specz.format.revision must agree with frame revision bytes. When config
precedence: environment path overrides, then site.conf, then defaults.conf. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2026-09-02 is retired; use
this entry for current operations.

## 2027-01-09 — Orphan fragments without manifest follow quarantine policy in incident 2024-041.

Operator log orphan-policy-0319. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When orphan
fragments without manifest follow quarantine policy in incident 2024-041. This entry
cross-references calibration labels in the container definition and the command
reference for public CLI behavior. Prior superseded note from 2026-09-11 is retired; use
this entry for current operations.

## 2027-01-18 — Initial SPECZ rev-1 raw 12-bit packing deployed for SPC07.

Operator log rev1-raw12-0320. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When initial specz
rev-1 raw 12-bit packing deployed for spc07. This entry cross-references calibration
labels in the container definition and the command reference for public CLI behavior.
Prior superseded note from 2026-09-20 is retired; use this entry for current operations.

## 2027-01-27 — Night shift reports inbox backlog; worker claims files atomically to work/.

Operator log spool-claim-0321. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When night shift
reports inbox backlog; worker claims files atomically to work/. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2026-09-29 is retired; use this entry
for current operations.

## 2027-02-05 — Calibration campaign SPC07 revision 11 coefficients archived.

Operator log cal-r11-0322. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When calibration
campaign spc07 revision 11 coefficients archived. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-10-08 is retired; use this entry for current
operations.

## 2027-02-14 — Hot-pixel mask list added to frame header; payload offset now variable.

Operator log mask-header-0323. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When hot-pixel mask
list added to frame header; payload offset now variable. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-10-17 is retired; use this entry for current
operations.

## 2027-02-23 — CRC computed over compressed payload bytes only (not decoded samples).

Operator log crc-payload-0324. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When crc computed
over compressed payload bytes only (not decoded samples). This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-10-26 is retired; use this entry for current
operations.

## 2027-03-04 — Revision 2 introduces optional delta8 payload encoding with 0x80 escapes.

Operator log rev2-delta-0325. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When revision 2
introduces optional delta8 payload encoding with 0x80 escapes. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2026-11-04 is retired; use this entry
for current operations.

## 2027-03-13 — reverse_pixels flag reverses decoded sample vector after unpacking.

Operator log rev-reverse-0326. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When reverse_pixels
flag reverses decoded sample vector after unpacking. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-11-13 is retired; use this entry for current
operations.

## 2027-03-22 — Temperature coefficient documented as picometers per degree Celsius.

Operator log temp-pm-0327. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When temperature
coefficient documented as picometers per degree celsius. This entry cross-references
calibration labels in the container definition and the command reference for public CLI
behavior. Prior superseded note from 2026-11-22 is retired; use this entry for current
operations.

Correction added to wavelength mapping as (temp_coeff_pm_per_C * (T_C - temp_ref_C)) / 1000.

## 2027-03-31 — Frame embedded calibration_revision selects coefficient tuple, not site default.

Operator log cal-rev-select-0328. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When frame embedded
calibration_revision selects coefficient tuple, not site default. This entry cross-
references calibration labels in the container definition and the command reference for
public CLI behavior. Prior superseded note from 2026-12-01 is retired; use this entry
for current operations.

## 2027-04-09 — Pixel indices are zero-based in all wavelength mapping.

Operator log zero-based-px-0329. During shift review we verified acquisition metadata,
detector temperature logs, and spool lifecycle counters. The active build label
org.obs.specz.format.revision must agree with frame revision bytes. When pixel indices
are zero-based in all wavelength mapping. This entry cross-references calibration labels
in the container definition and the command reference for public CLI behavior. Prior
superseded note from 2026-12-10 is retired; use this entry for current operations.

