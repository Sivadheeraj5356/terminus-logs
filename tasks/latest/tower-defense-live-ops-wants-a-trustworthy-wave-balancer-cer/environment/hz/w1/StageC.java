package hz.w1;

import cx.Jio;
import cx.SchedRow;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Stage C: seal packing only. */
public final class StageC {
    public static void main(String[] args) throws Exception {
        Path work = Path.of(System.getenv().getOrDefault("WORK_ROOT", "/tmp/wfc-work"));
        Path outRoot = Path.of(System.getenv().getOrDefault("OUT_ROOT", "/app/output"));
        Map<String, Object> wire = Jio.asMap(Jio.load(work.resolve("rows.json")));
        List<Object> rawRows = Jio.asList(wire.get("rows"));
        byte[] salt = hexToBytes(String.valueOf(wire.get("salt")));
        int digits = 4;
        try {
            Path env = Path.of(System.getenv().getOrDefault("ENV_ROOT", "/app/environment"));
            Map<String, Object> soft = Jio.asMap(Jio.load(env.resolve("pol/q_floor.json")));
            digits = ((Number) soft.get("digits")).intValue();
        } catch (Exception ignored) {
            // keep default
        }
        List<SchedRow> rows = new ArrayList<>();
        List<Object> emitRows = new ArrayList<>();
        for (Object o : rawRows) {
            Map<String, Object> m = Jio.asMap(o);
            String mid = String.valueOf(m.get("mid"));
            int idx = ((Number) m.get("idx")).intValue();
            String src = String.valueOf(m.get("src"));
            double press = round(((Number) m.get("press")).doubleValue(), digits);
            double left = round(((Number) m.get("left")).doubleValue(), digits);
            double leak = round(((Number) m.get("leak")).doubleValue(), digits);
            rows.add(new SchedRow(mid, idx, src, press, left, leak));
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("map_id", mid);
            row.put("wave_index", idx);
            row.put("spawn_hex", src);
            row.put("pressure_score", press);
            row.put("leftover_budget", left);
            row.put("leak_margin", leak);
            emitRows.add(row);
        }
        String seal = VmS8.vm_s8(rows, salt);
        Map<String, Object> emit = new LinkedHashMap<>();
        emit.put("rows", emitRows);
        emit.put("seal_hex", seal);
        Jio.save(outRoot.resolve("feasibility_cert.json"), emit);
    }

    private static double round(double v, int digits) {
        double s = Math.pow(10, digits);
        return Math.round(v * s) / s;
    }

    private static byte[] hexToBytes(String hex) {
        int n = hex.length();
        byte[] out = new byte[n / 2];
        for (int i = 0; i < out.length; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }
}
