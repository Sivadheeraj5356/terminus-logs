package gate;

import org.yaml.snakeyaml.Yaml;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ComposeLoader {

    private static final String BASE_FILE = "docker-compose.yml";
    private static final String OVERRIDE_FILE = "docker-compose.prod.yml";

    private ComposeLoader() { }

    @SuppressWarnings("unchecked")
    public static Map<String, Map<String, Object>> load(Path repoRoot) throws Exception {
        Map<String, Object> baseDoc = readYaml(repoRoot.resolve(BASE_FILE));
        Map<String, Object> overrideDoc = readYaml(repoRoot.resolve(OVERRIDE_FILE));
        if (baseDoc == null && overrideDoc == null) return Collections.emptyMap();

        Map<String, Object> baseSvcs = baseDoc == null
            ? new LinkedHashMap<>() : mapOrEmpty(baseDoc.get("services"));
        Map<String, Object> overrideSvcs = overrideDoc == null
            ? new LinkedHashMap<>() : mapOrEmpty(overrideDoc.get("services"));

        Map<String, Map<String, Object>> out = new LinkedHashMap<>();
        for (Map.Entry<String, Object> e : baseSvcs.entrySet()) {
            Map<String, Object> merged = new LinkedHashMap<>(mapOrEmpty(e.getValue()));
            Object ov = overrideSvcs.get(e.getKey());
            if (ov != null) mergeService(merged, mapOrEmpty(ov));
            out.put(e.getKey(), merged);
        }
        for (Map.Entry<String, Object> e : overrideSvcs.entrySet()) {
            if (baseSvcs.containsKey(e.getKey())) continue;
            out.put(e.getKey(), new LinkedHashMap<>(mapOrEmpty(e.getValue())));
        }
        return out;
    }

    @SuppressWarnings("unchecked")
    private static void mergeService(Map<String, Object> into, Map<String, Object> from) {
        for (Map.Entry<String, Object> e : from.entrySet()) {
            String key = e.getKey();
            Object v = e.getValue();
            if (v == null) { into.remove(key); continue; }
            if (v instanceof List) {
                // Every list-valued attribute replaces wholesale per §24.4.
                into.put(key, new ArrayList<>((List<Object>) v));
                continue;
            }
            Object base = into.get(key);
            if (v instanceof Map && base instanceof Map) {
                Map<String, Object> merged = new LinkedHashMap<>((Map<String, Object>) base);
                mergeMap(merged, (Map<String, Object>) v);
                into.put(key, merged);
            } else {
                into.put(key, v);
            }
        }
    }

    @SuppressWarnings("unchecked")
    private static void mergeMap(Map<String, Object> into, Map<String, Object> from) {
        for (Map.Entry<String, Object> e : from.entrySet()) {
            Object v = e.getValue();
            if (v == null) { into.remove(e.getKey()); continue; }
            Object base = into.get(e.getKey());
            if (v instanceof Map && base instanceof Map) {
                Map<String, Object> merged = new LinkedHashMap<>((Map<String, Object>) base);
                mergeMap(merged, (Map<String, Object>) v);
                into.put(e.getKey(), merged);
            } else {
                into.put(e.getKey(), v);
            }
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> mapOrEmpty(Object o) {
        if (o instanceof Map) return (Map<String, Object>) o;
        return new LinkedHashMap<>();
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
