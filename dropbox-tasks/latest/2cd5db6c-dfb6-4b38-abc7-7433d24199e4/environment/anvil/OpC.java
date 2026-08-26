package anvil;

import java.io.IOException;
import java.nio.file.Path;

/** Stamp and soname packaging stage. */
public final class OpC {
    private OpC() {}

    public static void main(String[] args) throws Exception {
        OpC(Path.of(args[0]), Path.of(args[1]));
    }

    /** Writes stamp bind, soname mark, and gate marker from opaque fixture maps. */
    public static void OpC(Path a, Path b) throws IOException {
        PackIo.ensureDir(b);
        String text = PackIo.read(a);
        long host = PackIo.num(text, "host_arch");
        PackIo.write(b.resolve("stamp.bind"), PackIo.str(text, "stamp_" + host));
        PackIo.write(b.resolve("soname.mark"), PackIo.str(text, "soname_" + host));
        PackIo.write(b.resolve("stub.gate"), "allow");
        if (a.getFileName() == null) {
            throw new IOException("missing fixture");
        }
    }
}
