package gp.u3;

import cx.Jio;
import cx.NamedSlot;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Stage A: bag assembly only. */
public final class StageA {
    public static void main(String[] args) throws Exception {
        Path env = Path.of(System.getenv().getOrDefault("ENV_ROOT", "/app/environment"));
        Path work = Path.of(System.getenv().getOrDefault("WORK_ROOT", "/tmp/wfc-work"));
        Path out = work.resolve("canon.json");
        List<Object> packs = new ArrayList<>();
        for (String rootName : List.of("m9", "z2")) {
            Path root = env.resolve("data").resolve(rootName);
            if (!Files.isDirectory(root)) {
                continue;
            }
            List<Path> dirs = sortedDirs(root);
            for (Path dir : dirs) {
                Map<String, Object> bag = Jio.asMap(Jio.load(dir.resolve("bag.json")));
                Map<String, Object> meta = Jio.asMap(Jio.load(dir.resolve("meta.json")));
                List<NamedSlot> slots = KnR4.kn_r4(bag);
                Map<String, Object> pack = new LinkedHashMap<>();
                pack.put("mid", String.valueOf(meta.get("map_id")));
                pack.put("seed", meta.get("seed"));
                List<Object> slotObjs = new ArrayList<>();
                for (NamedSlot s : slots) {
                    Map<String, Object> one = new LinkedHashMap<>();
                    one.put("n", s.name);
                    one.put("v", s.val);
                    slotObjs.add(one);
                }
                pack.put("slots", slotObjs);
                packs.add(pack);
            }
        }
        Map<String, Object> wire = new LinkedHashMap<>();
        wire.put("packs", packs);
        Jio.save(out, wire);
    }

    private static List<Path> sortedDirs(Path root) throws Exception {
        List<Path> dirs = new ArrayList<>();
        try (DirectoryStream<Path> ds = Files.newDirectoryStream(root)) {
            for (Path p : ds) {
                if (Files.isDirectory(p)) {
                    dirs.add(p);
                }
            }
        }
        dirs.sort((a, b) -> a.getFileName().toString().compareTo(b.getFileName().toString()));
        return dirs;
    }
}
