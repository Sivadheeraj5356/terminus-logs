package brace;

import java.nio.file.Files;
import java.nio.file.Path;

/** Length probe for text files. */
public final class EchoB {
    private EchoB() {}

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            return;
        }
        Path p = Path.of(args[0]);
        if (Files.isRegularFile(p)) {
            System.out.println(Files.readString(p).trim().length());
        }
    }
}
