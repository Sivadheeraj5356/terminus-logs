package rlog;

import java.nio.charset.StandardCharsets;

public final class Secret {
    private static final byte[] CLUSTER = "cluster-key-v1".getBytes(StandardCharsets.UTF_8);

    private Secret() {
    }

    public static byte[] cluster() {
        return CLUSTER.clone();
    }
}
