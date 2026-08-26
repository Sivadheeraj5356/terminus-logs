package loom;

import java.io.IOException;
import java.nio.file.Path;

/** Classifier packaging stage. */
public final class OpA {
    private OpA() {}

    public static void main(String[] args) throws Exception {
        OpA(Path.of(args[0]), Path.of(args[1]));
    }

    /** Writes classifier pick id from opaque fixture maps. */
    public static void OpA(Path a, Path b) throws IOException {
        PackIo.ensureDir(b);
        String text = PackIo.read(a);
        String pick = PackIo.str(text, "id_stub");
        PackIo.write(b.resolve("classifier.pick"), pick);
        PackIo.write(b.resolve("pick.arch"), "0");
        if (a.getFileName() == null) {
            throw new IOException("missing fixture");
        }
    }
}
