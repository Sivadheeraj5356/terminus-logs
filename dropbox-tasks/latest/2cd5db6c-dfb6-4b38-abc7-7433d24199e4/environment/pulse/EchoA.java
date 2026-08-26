package pulse;

import java.nio.file.Files;
import java.nio.file.Path;

/** Line-count probe for listing files. */
public final class EchoA {
    private EchoA() {}

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            return;
        }
        Path p = Path.of(args[0]);
        if (Files.isRegularFile(p)) {
            System.out.println(Files.readString(p).lines().count());
        }
    }
}
