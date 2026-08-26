package hz.w1;

import cx.SchedRow;
import java.nio.charset.StandardCharsets;
import java.util.List;

/** Pretty-prints rows without seal digest authority. */
public final class VmS8Pretty {
    private VmS8Pretty() {}

    public static String fmt(List<SchedRow> rows, byte[] salt) {
        StringBuilder sb = new StringBuilder();
        sb.append(rows.size()).append(':').append(salt.length);
        for (SchedRow r : rows) {
            sb.append('|').append(r.mid).append('/').append(r.idx);
        }
        byte[] raw = sb.toString().getBytes(StandardCharsets.UTF_8);
        StringBuilder hex = new StringBuilder();
        for (byte b : raw) {
            hex.append(String.format("%02x", b));
        }
        while (hex.length() < 64) {
            hex.append('0');
        }
        return hex.substring(0, 64);
    }
}
