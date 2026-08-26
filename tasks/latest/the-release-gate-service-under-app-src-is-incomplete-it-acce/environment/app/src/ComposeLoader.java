package gate;

import org.yaml.snakeyaml.Yaml;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/** Loads the compose model from the repository. */
public final class ComposeLoader {

    private ComposeLoader() { }

    @SuppressWarnings("unchecked")
    public static Map<String, Map<String, Object>> load(Path repoRoot) throws Exception {
        Path base = repoRoot.resolve("docker-compose.yml");
        Map<String, Object> baseDoc = readYaml(base);
        Map<String, Object> services = baseDoc == null ? null
            : (Map<String, Object>) baseDoc.get("services");
        if (services == null) return Collections.emptyMap();
        Map<String, Map<String, Object>> out = new LinkedHashMap<>();
        for (Map.Entry<String, Object> e : services.entrySet()) {
            Object v = e.getValue();
            if (v instanceof Map) {
                out.put(e.getKey(), (Map<String, Object>) v);
            } else {
                out.put(e.getKey(), new LinkedHashMap<>());
            }
        }
        return out;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> readYaml(Path p) throws Exception {
        if (!Files.exists(p)) return null;
        try (var r = Files.newBufferedReader(p)) {
            Yaml yaml = new Yaml();
            Object doc = yaml.load(r);
            if (doc instanceof Map) return (Map<String, Object>) doc;
            return null;
        }
    }
}
