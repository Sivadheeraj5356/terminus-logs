Restore the offline astronomy FITS-LITE recovery pipeline so that the command:

mosaicctl recover /app/data /app/work

will successfully reconstruct the calibrated sky mosaic from the immutable exposures of the individual sky tiles, along with the WCS metadata for each of those tiles, the reconciliation profile and epoch of the mosaic, the thresholds for contour detection, the coordinates of sample points within the mosaic, and the journal of the recovery of the interrupted pipeline. Build with the command:

make -C /app/environment clean all

Ensure that the data directory contents are preserved (i.e., must be byte-for-byte identical before and after running the recovery command). Ensure that all three work directories - the shipped interrupted work directory, the work directory emptied before running the recovery command, and the work directory emptied after publishing the mosaic - contain the same result. Invalid inputs must fail without modifying the last successfully-published version of the data directory.

The command should publish mosaic.fits, tile-order.manifest, mosaic-contours.svg, reconciliation-report.json, and recovery-status.json. Each of these files has a schema and rules for the values of their fields described in the reconciliation-contract.md and the /app/docs directories. The order of the individual tiles is stored in the file tile-order-authority.tsv. The active profile, epoch, and grid, and the global WCS for the mosaic are stored in the file run-config.tsv; tiles in ALT mode use the ALT WCS coordinates for placement within the mosaic. The recovery pipeline must be corrected; writing to the work directory outside of the reconciliation system is insufficient to accomplish the recovery. The normal reconciliation pipeline must be used to produce the published artifacts.

The commands:

mosaicctl audit <mosaic.fits>
mosaicctl render <mosaic.fits> <svg>
mosaicctl sample <mosaic.fits> <world_x> <world_y>

must produce the same results as the published artifacts. The reconciliation system must exhibit the same behavior when the order of the authority files is changed, or when the calibration of the system is uniformly scaled.