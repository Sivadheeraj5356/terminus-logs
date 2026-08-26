package anvil;

import java.nio.file.Path;

/** Stage entry that forwards to the packaging transform. */
public final class GateLoad {
    private GateLoad() {}

    public static void main(String[] args) throws Exception {
        OpC.OpC(Path.of(args[0]), Path.of(args[1]));
    }
}
