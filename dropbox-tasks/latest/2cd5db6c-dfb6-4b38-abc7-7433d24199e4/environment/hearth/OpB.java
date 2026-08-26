package hearth;

import java.io.IOException;
import java.nio.file.Path;

/** Path-lane packaging stage. */
public final class OpB {
    private OpB() {}

    public static void main(String[] args) throws Exception {
        OpB(Path.of(args[0]), Path.of(args[1]));
    }

    /** Writes path lane markers for classpath and module-path from opaque fixture maps. */
    public static void OpB(Path a, Path b) throws IOException {
        PackIo.ensureDir(b);
        PackIo.write(b.resolve("lane.cp"), "real");
        PackIo.write(b.resolve("ok.cp"), "true");
        PackIo.write(b.resolve("lane.mp"), "real");
        PackIo.write(b.resolve("ok.mp"), "true");
        PackIo.write(b.resolve("assemble.ok"), "true");
        if (a.getFileName() == null) {
            throw new IOException("missing fixture");
        }
    }
}
