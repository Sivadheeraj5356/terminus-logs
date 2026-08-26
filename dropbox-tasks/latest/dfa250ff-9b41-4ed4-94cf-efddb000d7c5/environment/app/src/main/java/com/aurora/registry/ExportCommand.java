package com.aurora.registry;

import java.nio.file.Path;
import java.sql.Connection;

/**
 * Writes the canonical promotion audit export.
 *
 * <p>The export is the artefact the review board signs off: it is reproduced independently and
 * compared byte for byte, so its layout, ordering, and numeric rendering are fixed by contract
 * rather than left to the writer. The contract lives in the 2027Q1 review dossier.
 */
public final class ExportCommand {

    /** Renders {@code promotion_audit} to {@code destination} in canonical form. */
    public void run(Connection connection, Path destination) throws Exception {
        throw new UnsupportedOperationException(
                "canonical promotion audit export is not implemented yet");
    }
}
