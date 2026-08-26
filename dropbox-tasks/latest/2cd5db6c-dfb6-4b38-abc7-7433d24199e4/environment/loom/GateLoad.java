package loom;

import java.nio.file.Path;

/** Stage entry that forwards to the packaging transform. */
public final class GateLoad {
    private GateLoad() {}

    public static void main(String[] args) throws Exception {
        OpA.OpA(Path.of(args[0]), Path.of(args[1]));
    }
}
