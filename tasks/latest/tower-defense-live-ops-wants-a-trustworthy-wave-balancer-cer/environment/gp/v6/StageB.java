package gp.v6;

import cx.Jio;
import cx.LimView;
import cx.NamedSlot;
import cx.SchedOut;
import cx.SchedRow;
import cx.SoftView;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Stage B: constrained search only. */
public final class StageB {
    public static void main(String[] args) throws Exception {
        Path env = Path.of(System.getenv().getOrDefault("ENV_ROOT", "/app/environment"));
        Path work = Path.of(System.getenv().getOrDefault("WORK_ROOT", "/tmp/wfc-work"));
        LimView lims = loadLims(env.resolve("pol/cap.toml"));
        SoftView softs = loadSoft(env.resolve("pol/q_floor.json"));
        Map<String, Object> wire = Jio.asMap(Jio.load(work.resolve("canon.json")));
        List<Object> packs = Jio.asList(wire.get("packs"));
        List<Object> allRows = new ArrayList<>();
        for (Object pObj : packs) {
            Map<String, Object> pack = Jio.asMap(pObj);
            String mid = String.valueOf(pack.get("mid"));
            List<NamedSlot> slots = new ArrayList<>();
            slots.add(new NamedSlot("__mid__", mid));
            for (Object sObj : Jio.asList(pack.get("slots"))) {
                Map<String, Object> s = Jio.asMap(sObj);
                slots.add(new NamedSlot(String.valueOf(s.get("n")), s.get("v")));
            }
            SchedOut out = LpQ2.lp_q2(slots, lims, softs);
            for (SchedRow r : out.rows) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("mid", r.mid);
                row.put("idx", r.idx);
                row.put("src", r.src);
                row.put("press", r.press);
                row.put("left", r.left);
                row.put("leak", r.leak);
                allRows.add(row);
            }
        }
        Map<String, Object> emit = new LinkedHashMap<>();
        emit.put("rows", allRows);
        emit.put("salt", bytesToHex(lims.salt));
        Jio.save(work.resolve("rows.json"), emit);
    }

    private static LimView loadLims(Path path) throws Exception {
        int maxCost = 30;
        double minLeft = 3.0;
        double maxAmp = 12.0;
        String saltHex = "00";
        for (String line : Files.readString(path).split("\n")) {
            String t = line.trim();
            if (t.startsWith("max_cost")) {
                maxCost = Integer.parseInt(t.split("=")[1].trim());
            } else if (t.startsWith("min_leftover")) {
                minLeft = Double.parseDouble(t.split("=")[1].trim());
            } else if (t.startsWith("max_amp")) {
                maxAmp = Double.parseDouble(t.split("=")[1].trim());
            } else if (t.startsWith("salt_hex")) {
                saltHex = t.split("=")[1].trim().replace("\"", "");
            }
        }
        return new LimView(maxCost, minLeft, maxAmp, hexToBytes(saltHex));
    }

    private static SoftView loadSoft(Path path) throws Exception {
        Map<String, Object> m = Jio.asMap(Jio.load(path));
        return new SoftView(
                ((Number) m.get("soft_floor")).doubleValue(),
                ((Number) m.get("egress_cap")).doubleValue(),
                ((Number) m.get("digits")).intValue());
    }

    private static byte[] hexToBytes(String hex) {
        int n = hex.length();
        byte[] out = new byte[n / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }

    private static String bytesToHex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte v : b) {
            sb.append(String.format("%02x", v));
        }
        return sb.toString();
    }
}
