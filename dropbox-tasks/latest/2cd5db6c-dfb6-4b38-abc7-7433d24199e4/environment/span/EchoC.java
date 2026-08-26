package span;

import java.nio.file.Files;
import java.nio.file.Path;

/** Non-blank line counter for label files. */
public final class EchoC {
    private EchoC() {}

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            return;
        }
        Path p = Path.of(args[0]);
        if (Files.isRegularFile(p)) {
            System.out.println(Files.readString(p).lines().filter(l -> !l.isBlank()).count());
        }
    }
}
